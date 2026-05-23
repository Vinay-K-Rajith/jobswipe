import hashlib
import re
from typing import Optional

import bcrypt
from fastapi import APIRouter, HTTPException, status
from jose import jwt
from pydantic import BaseModel, EmailStr, validator

from app.config import ADMIN_EMAIL_DOMAIN, ADMIN_LOGIN_PASSWORD, JWT_SECRET, STUDENT_EMAIL_DOMAIN, TRIAL_LOGIN_PASSWORD
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


def email_local_part(email: str) -> str:
    return email.strip().lower().split("@", 1)[0]


def name_from_email(email: str) -> str:
    local_part = email_local_part(email).replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return local_part.title() or "Trial User"


def company_from_email(email: str) -> str:
    domain = email_domain(email)
    return domain.split(".", 1)[0].replace("-", " ").title() or name_from_email(email)


def is_company_trial_email(email: str) -> bool:
    local_part = email_local_part(email)
    domain_parts = email_domain(email).split(".")
    return len(domain_parts) == 2 and domain_parts[1] == "com" and local_part == domain_parts[0]


def is_trial_password(password: str) -> bool:
    return password == TRIAL_LOGIN_PASSWORD


def supabase_maybe_single(table: str, column: str, value: str, select: str = "*"):
    try:
        return supabase.table(table).select(select).eq(column, value).maybe_single().execute()
    except Exception:
        return None


def supabase_insert(table: str, payload: dict):
    try:
        return supabase.table(table).insert(payload).execute()
    except Exception:
        return None


def create_trial_student(email: str, password: str) -> dict:
    local_part = email_local_part(email)
    student_id = local_part or "trial-student"
    payload = {
        "student_id": student_id,
        "register_number": student_id,
        "full_name": name_from_email(email),
        "name": name_from_email(email),
        "email": email,
        "password_hash": hash_password(password),
        "department": "CSE",
        "cgpa": 0,
        "year_of_study": 3,
    }
    result = supabase_insert("students", payload)
    if result and result.data:
        return result.data[0]
    return payload


def create_trial_recruiter(email: str, password: str) -> dict:
    company_name = company_from_email(email)
    payload = {
        "id": email,
        "name": name_from_email(email),
        "company_name": company_name,
        "company_domain": email_domain(email),
        "email": email,
        "password_hash": hash_password(password),
    }
    insert_payload = {key: value for key, value in payload.items() if key != "id"}
    supabase_insert("recruiters", insert_payload)
    result = supabase_maybe_single("recruiters", "email", email)
    if result and result.data:
        return result.data
    return payload


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

    existing = supabase_maybe_single("students", "register_number", req.register_number)
    if existing and existing.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Register number already exists")

    student_id = req.register_number
    supabase_insert("students", {
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
        email = str(req.email).lower()
        if not is_student_email(email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Student email must end with @{STUDENT_EMAIL_DOMAIN}")
        result = supabase_maybe_single("students", "email", email)
    elif req.register_number:
        result = supabase_maybe_single("students", "register_number", req.register_number)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    if not result or not result.data:
        if req.email and is_trial_password(req.password):
            student = create_trial_student(str(req.email).lower(), req.password)
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Student not found")
    else:
        student = result.data

    stored_hash = student.get("password_hash", "")
    if not is_trial_password(req.password) and (not stored_hash or not verify_password(req.password, stored_hash)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    student_id = student_id_from_record(student)
    email = str(req.email or student.get("email") or "")
    token = jwt.encode({"sub": student_id, "role": "student", "email": email}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "student_id": student_id, "name": student_name_from_record(student), "email": email}


@router.post("/recruiter/signup")
def recruiter_signup(req: RecruiterSignupRequest):
    email = str(req.email).lower()
    if not is_company_trial_email(email) or is_student_email(email) or is_admin_email(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company email must follow companyname@companyname.com")

    existing = supabase_maybe_single("recruiters", "email", email, "id")
    if existing and existing.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recruiter email already exists")

    supabase_insert("recruiters", {
        "name": req.name,
        "company_name": req.company_name,
        "company_domain": req.company_domain,
        "email": email,
        "password_hash": hash_password(req.password),
    }).execute()
    return {"message": "Signup successful"}


@router.post("/recruiter/login")
def recruiter_login(req: RecruiterLoginRequest):
    email = str(req.email).lower()
    if not is_company_trial_email(email) or is_student_email(email) or is_admin_email(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company email must follow companyname@companyname.com")

    result = supabase_maybe_single("recruiters", "email", email)
    if not result or not result.data:
        if is_trial_password(req.password):
            recruiter = create_trial_recruiter(email, req.password)
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Recruiter not found")
    else:
        recruiter = result.data

    if not is_trial_password(req.password) and not verify_password(req.password, recruiter.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    token = jwt.encode({"sub": recruiter["id"], "role": "recruiter", "email": email}, JWT_SECRET, algorithm="HS256")
    return {
        "access_token": token,
        "recruiter_id": recruiter["id"],
        "name": recruiter["name"],
        "company_name": recruiter["company_name"],
        "email": recruiter["email"],
    }


@router.post("/admin/login")
def admin_login(req: AdminLoginRequest):
    email = str(req.email).lower()
    if not is_admin_email(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Admin email must end with @{ADMIN_EMAIL_DOMAIN}")
    if req.password != ADMIN_LOGIN_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    token = jwt.encode({"sub": email, "role": "admin", "email": email}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "admin_id": email, "name": "Placement Team", "email": email}
