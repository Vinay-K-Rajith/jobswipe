import hashlib
import re
from typing import List, Optional

import bcrypt
from fastapi import APIRouter, HTTPException, status
from jose import jwt
from pydantic import BaseModel, EmailStr, validator

from app.config import ADMIN_EMAIL_DOMAIN, ADMIN_LOGIN_PASSWORD, JWT_SECRET, STUDENT_EMAIL_DOMAIN, TRIAL_LOGIN_PASSWORD
from app.database import supabase

router = APIRouter(prefix="/auth", tags=["auth"])
REG_PATTERN = re.compile(r"^RA\d{13}$")
GENERIC_COMPANY_TOKENS = {
    "and",
    "center",
    "company",
    "corp",
    "corporation",
    "development",
    "global",
    "india",
    "indian",
    "limited",
    "ltd",
    "private",
    "pvt",
    "systems",
    "technologies",
    "technology",
}


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


def supabase_select_students(select: str = "*") -> List[dict]:
    try:
        result = supabase.table("students").select(select).execute()
        return result.data or []
    except Exception:
        return []


def supabase_select_recruiters(select: str = "*") -> List[dict]:
    try:
        result = supabase.table("recruiters").select(select).execute()
        return result.data or []
    except Exception:
        return []


def supabase_select_jobs(select: str = "*") -> List[dict]:
    try:
        result = supabase.table("jobs").select(select).execute()
        return result.data or []
    except Exception:
        return []


def supabase_update(table: str, payload: dict, column: str, value: str):
    try:
        return supabase.table(table).update(payload).eq(column, value).execute()
    except Exception:
        return None


def account_tokens(value: str) -> List[str]:
    return [token for token in re.split(r"[^a-z0-9]+", str(value or "").lower()) if token]


def company_match_tokens(value: str) -> set:
    return {token for token in account_tokens(value) if token not in GENERIC_COMPANY_TOKENS}


def is_placeholder_student(student: Optional[dict]) -> bool:
    if not student:
        return False
    sid = str(student.get("student_id") or "")
    register_number = str(student.get("register_number") or "")
    email = str(student.get("email") or "").lower()
    local_part = email_local_part(email) if email else ""
    cgpa = float(student.get("cgpa") or 0)
    year_of_study = int(student.get("year_of_study") or 0)
    return (
        bool(local_part)
        and sid == local_part
        and register_number == local_part
        and cgpa == 0
        and year_of_study == 3
    )


def canonical_student_match(email: str) -> Optional[dict]:
    local_part = email_local_part(email)
    display_name = name_from_email(email).lower()
    search_tokens = set(account_tokens(local_part) + account_tokens(display_name))
    if not search_tokens:
        return None

    rows = supabase_select_students("student_id, register_number, full_name, name, email, password_hash, department, cgpa, year_of_study, batch_year")
    best_row = None
    best_key = None
    for row in rows:
        if is_placeholder_student(row):
            continue
        full_name = str(row.get("full_name") or row.get("name") or "").strip().lower()
        row_tokens = set(account_tokens(full_name) + account_tokens(row.get("student_id") or "") + account_tokens(row.get("register_number") or ""))
        score = len(search_tokens & row_tokens)
        if full_name == display_name:
            score += 6
        if full_name.startswith(f"{local_part} "):
            score += 4
        if row.get("student_id") and str(row["student_id"]).lower() == local_part:
            score += 10
        if row.get("register_number") and str(row["register_number"]).lower() == local_part:
            score += 10
        if score <= 0:
            continue
        sort_key = (score, float(row.get("cgpa") or 0), -len(full_name), str(row.get("student_id") or ""))
        if best_key is None or sort_key > best_key:
            best_key = sort_key
            best_row = row
    return best_row


def company_tokens_from_email(email: str) -> set:
    domain = email_domain(email).split(".", 1)[0]
    local_part = email_local_part(email)
    return company_match_tokens(local_part) | company_match_tokens(domain)


def recruiter_sort_key(row: dict, search_tokens: set) -> tuple:
    company_name = str(row.get("company_name") or "").strip().lower()
    company_domain = str(row.get("company_domain") or "").strip().lower()
    email = str(row.get("email") or "").strip().lower()
    row_tokens = set(
        list(company_match_tokens(company_name))
        + list(company_match_tokens(company_domain))
        + list(company_match_tokens(email_local_part(email) if email else ""))
        + list(company_match_tokens(email_domain(email).split(".", 1)[0] if email else ""))
    )
    score = len(search_tokens & row_tokens)
    if company_name and company_name.replace(" ", "") in search_tokens:
        score += 6
    if company_domain and company_domain.split(".", 1)[0] in search_tokens:
        score += 6
    return (score, bool(row.get("id")), company_name)


def canonical_recruiter_match(email: str) -> Optional[dict]:
    search_tokens = company_tokens_from_email(email)
    if not search_tokens:
        return None

    rows = supabase_select_recruiters("id, name, company_name, company_domain, email, password_hash")
    best_row = None
    best_key = None
    for row in rows:
        sort_key = recruiter_sort_key(row, search_tokens)
        if sort_key[0] <= 0:
            continue
        if best_key is None or sort_key > best_key:
            best_key = sort_key
            best_row = row
    return best_row


def canonical_company_from_jobs(email: str) -> Optional[str]:
    search_tokens = company_tokens_from_email(email)
    if not search_tokens:
        return None

    best_name = None
    best_key = None
    for row in supabase_select_jobs("company_name"):
        company_name = str(row.get("company_name") or "").strip()
        if not company_name:
            continue
        row_tokens = company_match_tokens(company_name)
        score = len(search_tokens & row_tokens)
        compact_name = company_name.lower().replace(" ", "")
        if compact_name in search_tokens:
            score += 6
        if score <= 0:
            continue
        sort_key = (score, -len(company_name), company_name.lower())
        if best_key is None or sort_key > best_key:
            best_key = sort_key
            best_name = company_name
    return best_name


def attach_seed_jobs_to_recruiter(recruiter: dict) -> None:
    recruiter_id = recruiter.get("id")
    company_name = str(recruiter.get("company_name") or "").strip()
    if not recruiter_id or not company_name:
        return

    recruiter_tokens = company_match_tokens(company_name)
    if not recruiter_tokens:
        return

    for job in supabase_select_jobs("id, company_name, recruiter_id"):
        if job.get("recruiter_id"):
            continue
        job_company = str(job.get("company_name") or "").strip()
        if not job_company:
            continue
        job_tokens = company_match_tokens(job_company)
        if job_company.lower() == company_name.lower() or recruiter_tokens & job_tokens:
            supabase_update("jobs", {"recruiter_id": recruiter_id}, "id", job["id"])


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
    company_name = canonical_company_from_jobs(email) or company_from_email(email)
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
        recruiter = result.data
    else:
        recruiter = payload
    attach_seed_jobs_to_recruiter(recruiter)
    return recruiter


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
    email = None
    if req.email:
        email = str(req.email).lower()
        if not is_student_email(email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Student email must end with @{STUDENT_EMAIL_DOMAIN}")
        result = supabase_maybe_single("students", "email", email)
    elif req.register_number:
        result = supabase_maybe_single("students", "register_number", req.register_number)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    student = result.data if result and result.data else None
    matched_student = canonical_student_match(email) if email else None

    if matched_student and (not student or is_placeholder_student(student)):
        student = matched_student

    if not student:
        if req.email and is_trial_password(req.password):
            student = create_trial_student(str(req.email).lower(), req.password)
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Student not found")

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
    matched_recruiter = canonical_recruiter_match(email)
    if not result or not result.data:
        if matched_recruiter and is_trial_password(req.password):
            recruiter = matched_recruiter
        elif is_trial_password(req.password):
            recruiter = create_trial_recruiter(email, req.password)
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Recruiter not found")
    else:
        recruiter = result.data

    if not is_trial_password(req.password) and not verify_password(req.password, recruiter.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    attach_seed_jobs_to_recruiter(recruiter)

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
