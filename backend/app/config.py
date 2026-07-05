import os
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
STUDENT_EMAIL_DOMAIN = os.getenv("STUDENT_EMAIL_DOMAIN", "srmist.edu.in").lower()
ADMIN_EMAIL_DOMAIN = os.getenv("ADMIN_EMAIL_DOMAIN", "admin.com").lower()
ADMIN_LOGIN_PASSWORD = os.getenv("ADMIN_LOGIN_PASSWORD", "Test123")
TRIAL_LOGIN_PASSWORD = os.getenv("TRIAL_LOGIN_PASSWORD", "Test123")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", 8000))
JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", 12))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL not set in .env")
