"""
Supabase Client: shim that returns a PostgresClient (direct connection-string
backend) with the same API surface as supabase-py.
"""

from app.db.postgres_client import PostgresClient, get_postgres_client

_client: PostgresClient | None = None


def get_client(_use_service_key: bool = False) -> PostgresClient:
    global _client
    if _client is None:
        _client = get_postgres_client()
    return _client


def test_connection() -> bool:
    try:
        client = get_client()
        client.table("students").select("student_id").limit(1).execute()
        print("✅ Connected to Supabase (direct Postgres)")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()
