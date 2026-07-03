"""
Drop-in replacement for the supabase-py client that runs over a raw
psycopg2 connection string.  Implements the subset of the supabase-py
builder API actually used in this codebase.

Supported chain:
  client.table(name)
    .select(cols) / .insert(data) / .update(data) / .delete() / .upsert(data, on_conflict=)
    .eq(col, val) / .in_(col, vals) / .like(col, pat) / .match({...})
    .order(col, desc=False) / .limit(n)
    .maybe_single() / .single()
    .execute()  →  APIResponse(data=...)
"""

import json
import os
import re
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# Load .env relative to this file's location (backend/.env)
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

_pool_lock = threading.Lock()
_connection: Optional[psycopg2.extensions.connection] = None


def _get_connection(dsn: str) -> psycopg2.extensions.connection:
    global _connection
    with _pool_lock:
        if _connection is None or _connection.closed:
            _connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
            _connection.autocommit = True
        else:
            try:
                _connection.cursor().execute("SELECT 1")
            except Exception:
                _connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
                _connection.autocommit = True
        return _connection


def _serialize(value: Any) -> Any:
    """Convert a Python value to something psycopg2 can bind cleanly."""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def _normalize_row(row: dict) -> dict:
    """Convert datetime objects in a result row to ISO strings."""
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, date):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


class APIResponse:
    def __init__(self, data: Any):
        self.data = data

    def __bool__(self):
        return True


class QueryBuilder:
    def __init__(self, table: str, dsn: str):
        self._table = table
        self._dsn = dsn
        self._operation: str = "select"
        self._select_cols: str = "*"
        self._embed_join: Optional[str] = None  # foreign table to LEFT JOIN
        self._data: Any = None
        self._on_conflict: Optional[str] = None
        self._filters: List[str] = []
        self._params: List[Any] = []
        self._order_col: Optional[str] = None
        self._order_desc: bool = False
        self._limit_n: Optional[int] = None
        self._single_mode: bool = False  # maybe_single / single
        self._returning: bool = False    # .update().select() → RETURNING *

    # ------------------------------------------------------------------ #
    # Operation starters                                                   #
    # ------------------------------------------------------------------ #

    def select(self, cols: str = "*") -> "QueryBuilder":
        if self._operation in ("update", "delete"):
            # chained .select() after update → RETURNING
            self._returning = True
            return self
        self._operation = "select"
        # Detect embedded foreign-table syntax: "*,jobs(*)"
        m = re.match(r"^\*,(\w+)\(\*\)$", cols.replace(" ", ""))
        if m:
            self._embed_join = m.group(1)
            self._select_cols = "*"
        else:
            self._select_cols = cols
        return self

    def insert(self, data: Union[Dict, List]) -> "QueryBuilder":
        self._operation = "insert"
        self._data = data if isinstance(data, list) else [data]
        return self

    def update(self, data: Dict) -> "QueryBuilder":
        self._operation = "update"
        self._data = data
        return self

    def upsert(self, data: Union[Dict, List], on_conflict: Optional[str] = None) -> "QueryBuilder":
        self._operation = "upsert"
        self._data = data if isinstance(data, list) else [data]
        self._on_conflict = on_conflict
        return self

    def delete(self) -> "QueryBuilder":
        self._operation = "delete"
        return self

    # ------------------------------------------------------------------ #
    # Filters                                                              #
    # ------------------------------------------------------------------ #

    def eq(self, col: str, val: Any) -> "QueryBuilder":
        self._filters.append(f'"{col}" = %s')
        self._params.append(_serialize(val))
        return self

    def in_(self, col: str, vals: List) -> "QueryBuilder":
        placeholders = ",".join(["%s"] * len(vals))
        self._filters.append(f'"{col}" IN ({placeholders})')
        self._params.extend([_serialize(v) for v in vals])
        return self

    def like(self, col: str, pattern: str) -> "QueryBuilder":
        self._filters.append(f'"{col}" LIKE %s')
        self._params.append(pattern)
        return self

    def match(self, filters: Dict) -> "QueryBuilder":
        for col, val in filters.items():
            self.eq(col, val)
        return self

    # ------------------------------------------------------------------ #
    # Ordering / pagination                                                #
    # ------------------------------------------------------------------ #

    def order(self, col: str, desc: bool = False) -> "QueryBuilder":
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n: int) -> "QueryBuilder":
        self._limit_n = n
        return self

    # ------------------------------------------------------------------ #
    # Fetch modifiers                                                      #
    # ------------------------------------------------------------------ #

    def maybe_single(self) -> "QueryBuilder":
        self._single_mode = True
        if self._limit_n is None:
            self._limit_n = 1
        return self

    def single(self) -> "QueryBuilder":
        return self.maybe_single()

    # ------------------------------------------------------------------ #
    # Execute                                                              #
    # ------------------------------------------------------------------ #

    def execute(self) -> APIResponse:
        conn = _get_connection(self._dsn)
        with conn.cursor() as cur:
            if self._operation == "select":
                return self._exec_select(cur)
            elif self._operation == "insert":
                return self._exec_insert(cur)
            elif self._operation == "update":
                return self._exec_update(cur)
            elif self._operation == "upsert":
                return self._exec_upsert(cur)
            elif self._operation == "delete":
                return self._exec_delete(cur)
            else:
                raise ValueError(f"Unknown operation: {self._operation}")

    # ------------------------------------------------------------------ #
    # Private SQL builders                                                 #
    # ------------------------------------------------------------------ #

    def _where_clause(self) -> str:
        if not self._filters:
            return ""
        return " WHERE " + " AND ".join(self._filters)

    def _suffix(self) -> str:
        parts = []
        if self._order_col:
            direction = "DESC" if self._order_desc else "ASC"
            parts.append(f'ORDER BY "{self._order_col}" {direction}')
        if self._limit_n is not None:
            parts.append(f"LIMIT {int(self._limit_n)}")
        return (" " + " ".join(parts)) if parts else ""

    def _exec_select(self, cur) -> APIResponse:
        table = self._table
        if self._embed_join:
            join_table = self._embed_join
            join_fk = join_table.rstrip("s") + "_id"
            sql = (
                f'SELECT t.*, row_to_json(j.*) AS "{join_table}" '
                f'FROM "{table}" t '
                f'LEFT JOIN "{join_table}" j ON j.id = t."{join_fk}"'
            )
        else:
            cols = self._select_cols if self._select_cols != "*" else "*"
            if cols != "*":
                quoted = ", ".join(f'"{c.strip()}"' for c in cols.split(","))
                sql = f'SELECT {quoted} FROM "{table}"'
            else:
                sql = f'SELECT * FROM "{table}"'

        sql += self._where_clause() + self._suffix()
        cur.execute(sql, self._params)
        rows = [_normalize_row(dict(r)) for r in cur.fetchall()]

        if self._single_mode:
            return APIResponse(rows[0] if rows else None)
        return APIResponse(rows)

    def _exec_insert(self, cur) -> APIResponse:
        if not self._data:
            return APIResponse([])
        rows = self._data
        cols = list(rows[0].keys())
        quoted_cols = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(["%s"] * len(cols))
        sql = f'INSERT INTO "{self._table}" ({quoted_cols}) VALUES ({placeholders}) RETURNING *'
        results = []
        for row in rows:
            vals = [_serialize(row.get(c)) for c in cols]
            cur.execute(sql, vals)
            inserted = cur.fetchone()
            if inserted:
                results.append(_normalize_row(dict(inserted)))
        return APIResponse(results)

    def _exec_update(self, cur) -> APIResponse:
        if not self._data:
            return APIResponse([])
        data = self._data
        set_parts = [f'"{k}" = %s' for k in data.keys()]
        set_vals = [_serialize(v) for v in data.values()]
        returning = " RETURNING *" if self._returning else ""
        sql = (
            f'UPDATE "{self._table}" SET {", ".join(set_parts)}'
            + self._where_clause()
            + returning
        )
        cur.execute(sql, set_vals + self._params)
        if self._returning:
            rows = [_normalize_row(dict(r)) for r in cur.fetchall()]
            return APIResponse(rows)
        return APIResponse([])

    def _exec_upsert(self, cur) -> APIResponse:
        if not self._data:
            return APIResponse([])
        rows = self._data
        cols = list(rows[0].keys())
        quoted_cols = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(["%s"] * len(cols))

        if self._on_conflict:
            conflict_cols = [c.strip() for c in self._on_conflict.split(",")]
            conflict_target = ", ".join(f'"{c}"' for c in conflict_cols)
            update_parts = ", ".join(
                f'"{c}" = EXCLUDED."{c}"'
                for c in cols
                if c not in conflict_cols
            )
            on_conflict_clause = (
                f"ON CONFLICT ({conflict_target}) DO UPDATE SET {update_parts}"
                if update_parts
                else f"ON CONFLICT ({conflict_target}) DO NOTHING"
            )
        else:
            on_conflict_clause = "ON CONFLICT DO NOTHING"

        sql = (
            f'INSERT INTO "{self._table}" ({quoted_cols}) VALUES ({placeholders})'
            f" {on_conflict_clause} RETURNING *"
        )
        results = []
        for row in rows:
            vals = [_serialize(row.get(c)) for c in cols]
            cur.execute(sql, vals)
            inserted = cur.fetchone()
            if inserted:
                results.append(_normalize_row(dict(inserted)))
        return APIResponse(results)

    def _exec_delete(self, cur) -> APIResponse:
        sql = f'DELETE FROM "{self._table}"' + self._where_clause()
        cur.execute(sql, self._params)
        return APIResponse([])


class PostgresClient:
    """Supabase-py compatible client backed by direct psycopg2."""

    def __init__(self, dsn: str):
        self._dsn = dsn
        # Verify connectivity eagerly
        _get_connection(dsn)

    def table(self, name: str) -> QueryBuilder:
        return QueryBuilder(name, self._dsn)


def get_postgres_client() -> PostgresClient:
    """Return a module-level singleton PostgresClient from SUPABASE_URL."""
    dsn = os.getenv("SUPABASE_URL", "")
    if not dsn:
        raise RuntimeError("SUPABASE_URL not set in .env")
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError(
            "SUPABASE_URL must be a postgresql:// connection string "
            f"(got: {dsn[:30]}...)"
        )
    # Append sslmode=require if not present
    if "sslmode" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
    return PostgresClient(dsn)
