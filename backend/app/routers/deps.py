from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import JWT_SECRET
from app.database import supabase

bearer_scheme = HTTPBearer()


def email_local_part(email: str) -> str:
    return email.strip().lower().split("@", 1)[0]


def email_domain(email: str) -> str:
    return email.strip().lower().split("@")[-1]


def name_from_email(email: str) -> str:
    local_part = email_local_part(email).replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return local_part.title() or "Trial User"


def company_from_email(email: str) -> str:
    return email_domain(email).split(".", 1)[0].replace("-", " ").title() or name_from_email(email)


def decode_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    if not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload


def get_current_user(payload=Depends(decode_token)):
    if payload.get("role") != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student token required")

    student_id = payload["sub"]
    try:
        user_result = supabase.table("students").select("*").eq("student_id", student_id).maybe_single().execute()
        user = user_result.data if user_result else None
        if not user:
            user_result = supabase.table("students").select("*").eq("id", student_id).maybe_single().execute()
            user = user_result.data if user_result else None
    except Exception:
        email = str(payload.get("email") or "")
        user = {
            "student_id": student_id,
            "id": student_id,
            "register_number": student_id,
            "full_name": name_from_email(email),
            "name": name_from_email(email),
            "email": email,
        }
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    user["role"] = "student"
    return user


def get_current_recruiter(payload=Depends(decode_token)):
    if payload.get("role") != "recruiter":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recruiter token required")

    recruiter_id = payload["sub"]
    try:
        user_result = supabase.table("recruiters").select("*").eq("id", recruiter_id).maybe_single().execute()
        user = user_result.data if user_result else None
    except Exception:
        email = str(payload.get("email") or recruiter_id)
        user = {
            "id": recruiter_id,
            "name": name_from_email(email),
            "company_name": company_from_email(email),
            "company_domain": email_domain(email),
            "email": email,
        }
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Recruiter not found")
    user["role"] = "recruiter"
    return user


def get_current_any_user(payload=Depends(decode_token)):
    role = payload.get("role")
    if role == "student":
        return {"role": "student", "user": get_current_user(payload)}
    if role == "recruiter":
        return {"role": "recruiter", "user": get_current_recruiter(payload)}
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student or recruiter token required")
