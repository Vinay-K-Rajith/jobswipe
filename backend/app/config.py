import os
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")

BACKEND_PORT = int(os.getenv("BACKEND_PORT", 8000))

if not SUPABASE_URL or not SUPABASE_ANON_KEY or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("Supabase URL/keys are missing in .env")
