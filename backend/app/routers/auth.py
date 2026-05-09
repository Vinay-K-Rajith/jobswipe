import hashlib
import re
from typing import Optional

import bcrypt
from fastapi import APIRouter, HTTPException, status
from jose import jwt
from pydantic import BaseModel, EmailStr, validator

from app.config import ADMIN_EMAIL_DOMAIN, ADMIN_LOGIN_PASSWORD, JWT_SECRET, STUDENT_EMAIL_DOMAIN
from app.database import supabase

router = APIRouter(prefix="/auth", tags=["auth"])
REG_PATTERN = re.compile(r"^RA\d{13}$")


def email_domain(email: str) -> str:
    return email.strip().lower().split("@")[-1]


def is_student_email(email: str) -> bool:
    return email_domain(email) == STUDENT_EMAIL_DOMAIN


def is_admin_email(email: str) -> bool:
    return email_domain(email) == ADMIN_EMAIL_DOMAIN


def hash_password(password: str) -> str:
    sha256_hash = hashlib.sha256(password.encode()).hexdigest()
    return bcrypt.hashpw(sha256_hash.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    sha256_hash = hashlib.sha256(password.encode()).hexdigest()
    return bcrypt.checkpw(sha256_hash.encode(), stored_hash.encode())


def student_id_from_record(student: dict) -> str:
    return str(student.get("student_id") or student.get("id") or student.get("register_number"))


def student_name_from_record(student: dict) -> str:
    return str(student.get("full_name") or student.get("name") or student.get("register_number") or "Student")


class StudentSignupRequest(BaseModel):
    name: str
    register_number: str
    email: EmailStr
    password: str

    @validator("register_number")
    def validate_reg(cls, value):
        if not REG_PATTERN.match(value):
            raise ValueError("Register number must follow pattern RA2311047010209")
        return value


class StudentLoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    register_number: Optional[str] = None
    password: str


class RecruiterSignupRequest(BaseModel):
    name: str
    company_name: str
    company_domain: str
    email: EmailStr
    password: str


class RecruiterLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/student/signup")
@router.post("/signup")
def student_signup(req: StudentSignupRequest):
    if not is_student_email(str(req.email)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Student email must end with @{STUDENT_EMAIL_DOMAIN}")

    existing = supabase.table("students").select("*").eq("register_number", req.register_number).maybe_single().execute()
    if existing and existing.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Register number already exists")

    student_id = req.register_number
    supabase.table("students").insert({
        "student_id": student_id,
        "register_number": req.register_number,
        "full_name": req.name,
        "name": req.name,
        "email": str(req.email),
        "password_hash": hash_password(req.password),
        "department": "CSE",
        "cgpa": 0,
        "year_of_study": 3,
    }).execute()
    return {"message": "Signup successful"}


@router.post("/student/login")
@router.post("/login")
def student_login(req: StudentLoginRequest):
    if req.email:
        result = supabase.table("students").select("*").eq("email", str(req.email)).maybe_single().execute()
    elif req.register_number:
        result = supabase.table("students").select("*").eq("register_number", req.register_number).maybe_single().execute()
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Student not found")

    student = result.data
    stored_hash = student.get("password_hash", "")
    if not stored_hash or not verify_password(req.password, stored_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    student_id = student_id_from_record(student)
    email = str(req.email or student.get("email") or "")
    token = jwt.encode({"sub": student_id, "role": "student", "email": email}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "student_id": student_id, "name": student_name_from_record(student), "email": email}


@router.post("/recruiter/signup")
def recruiter_signup(req: RecruiterSignupRequest):
    if is_student_email(str(req.email)) or is_admin_email(str(req.email)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recruiter email must use a company domain")

    existing = supabase.table("recruiters").select("id").eq("email", str(req.email)).maybe_single().execute()
    if existing and existing.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recruiter email already exists")

    supabase.table("recruiters").insert({
        "name": req.name,
        "company_name": req.company_name,
        "company_domain": req.company_domain,
        "email": str(req.email),
        "password_hash": hash_password(req.password),
    }).execute()
    return {"message": "Signup successful"}


@router.post("/recruiter/login")
def recruiter_login(req: RecruiterLoginRequest):
    result = supabase.table("recruiters").select("*").eq("email", str(req.email)).maybe_single().execute()
    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Recruiter not found")

    recruiter = result.data
    if not verify_password(req.password, recruiter.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    token = jwt.encode({"sub": recruiter["id"], "role": "recruiter", "email": str(req.email)}, JWT_SECRET, algorithm="HS256")
    return {
        "access_token": token,
        "recruiter_id": recruiter["id"],
        "name": recruiter["name"],
        "company_name": recruiter["company_name"],
        "email": recruiter["email"],
    }


@router.post("/admin/login")
def admin_login(req: AdminLoginRequest):
    if not is_admin_email(str(req.email)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Admin email must end with @{ADMIN_EMAIL_DOMAIN}")
    if req.password != ADMIN_LOGIN_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    token = jwt.encode({"sub": str(req.email), "role": "admin", "email": str(req.email)}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "admin_id": str(req.email), "name": "Placement Team", "email": str(req.email)}
