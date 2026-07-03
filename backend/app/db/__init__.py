"""Database access layer.

Exposes :func:`get_postgres_client`, a drop-in replacement for the supabase-py
client that talks to PostgreSQL directly via a connection string (no API keys
required). See :mod:`app.db.postgres_client` for the full compatibility surface.
"""

from app.db.postgres_client import PostgresClient, get_postgres_client

__all__ = ["PostgresClient", "get_postgres_client"]
