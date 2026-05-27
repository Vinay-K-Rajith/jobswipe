import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import supabase
from app.routers.deps import get_current_recruiter, get_current_user
from app.services.cache_control import clear_profile_dependent_caches

router = APIRouter(prefix="/profile", tags=["profile"])
RECRUITER_PROFILE_STORE = Path(__file__).resolve().parents[2] / "data" / "recruiter_profiles_local.json"


class ProfileSkillUpdate(BaseModel):
    name: str
    proficiency: str = "Not set"


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    personal_email: Optional[str] = None
    college_email: Optional[str] = None
    phone_number: Optional[str] = None
    register_number: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    college_name: Optional[str] = None
    tenth_marks: Optional[float] = Field(default=None, alias="class_10_marks")
    tenth_board: Optional[str] = Field(default=None, alias="class_10_board")
    twelfth_marks: Optional[float] = Field(default=None, alias="class_12_marks")
    twelfth_board: Optional[str] = Field(default=None, alias="class_12_board")
    cgpa: Optional[float] = None
    active_backlogs: Optional[int] = None
    backlog_history: Optional[int] = None
    year_of_study: Optional[int] = None
    batch_year: Optional[int] = None
    preferred_roles: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    looking_for: Optional[str] = None
    remote_preference: Optional[str] = None
    open_to_relocation: Optional[bool] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    coding_profile_url: Optional[str] = None

    model_config = {"populate_by_name": True}


class SkillsUpdate(BaseModel):
    skills: List[ProfileSkillUpdate]


class RecruiterProfileUpdate(BaseModel):
    name: Optional[str] = None
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    designation: Optional[str] = None
    phone_number: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    hiring_type: Optional[str] = None
    preferred_departments: Optional[List[str]] = None
    preferred_graduation_years: Optional[List[int]] = None
    min_cgpa: Optional[float] = None
    max_active_backlogs: Optional[int] = None
    work_mode: Optional[str] = None
    about_company: Optional[str] = None
    hiring_pitch: Optional[str] = None
    website_url: Optional[str] = None
    careers_url: Optional[str] = None
    linkedin_url: Optional[str] = None


def current_student_key(user: Dict[str, Any]) -> str:
    return str(user.get("student_id") or user.get("id") or user.get("register_number"))


def load_student_by_student_id(student_id: str) -> Dict[str, Any]:
    result = supabase.table("students").select("*").eq("student_id", student_id).maybe_single().execute()
    student = result.data if result else None
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student


def normalize_text_list(values: Optional[List[str]]) -> List[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def load_recruiter_profiles() -> Dict[str, Any]:
    if not RECRUITER_PROFILE_STORE.exists():
        return {}
    try:
        return json.loads(RECRUITER_PROFILE_STORE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_recruiter_profiles(profiles: Dict[str, Any]) -> None:
    RECRUITER_PROFILE_STORE.parent.mkdir(parents=True, exist_ok=True)
    RECRUITER_PROFILE_STORE.write_text(json.dumps(profiles, indent=2), encoding="utf-8")


def recruiter_profile_meta(recruiter_id: str) -> Dict[str, Any]:
    return dict(load_recruiter_profiles().get(str(recruiter_id), {}) or {})


def count_rows(table: str, filters: Dict[str, Any]) -> int:
    try:
        query = supabase.table(table).select("id")
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.execute()
        return len(result.data or []) if result else 0
    except Exception:
        return 0


def recruiter_student_interest_count(recruiter_id: str) -> int:
    try:
        jobs_result = supabase.table("jobs").select("id").eq("recruiter_id", recruiter_id).execute()
        job_ids = [row.get("id") for row in (jobs_result.data or []) if row.get("id")]
        if not job_ids:
            return 0
        result = supabase.table("student_interest").select("id").in_("job_id", job_ids).execute()
        return len(result.data or []) if result else 0
    except Exception:
        return 0


@router.patch("/{student_id}")
def update_profile(student_id: str, data: ProfileUpdate, user=Depends(get_current_user)):
    if current_student_key(user) != student_id:
        raise HTTPException(status_code=403, detail="You can only update your own profile")

    student = load_student_by_student_id(student_id)
    payload = data.model_dump(by_alias=True, exclude_unset=True)

    db_updates: Dict[str, Any] = {}
    direct_map = {
        "full_name": "full_name",
        "register_number": "register_number",
        "department": "department",
        "branch": "branch",
        "college_name": "college_name",
        "class_10_marks": "10th_marks",
        "class_10_board": "10th_board",
        "class_12_marks": "12th_marks",
        "class_12_board": "12th_board",
        "cgpa": "cgpa",
        "active_backlogs": "active_backlogs",
        "backlog_history": "backlogs_history",
        "year_of_study": "year_of_study",
        "batch_year": "batch_year",
        "portfolio_url": "portfolio_url",
    }
    for incoming_key, db_key in direct_map.items():
        if incoming_key in payload:
            db_updates[db_key] = payload[incoming_key]

    if "college_email" in payload and payload["college_email"] is not None:
        db_updates["email"] = payload["college_email"]

    meta_source = student.get("resume_parse_confidence") or {}
    profile_meta = dict(meta_source.get("profile_meta") or {})
    meta_keys = [
        "full_name",
        "personal_email",
        "college_email",
        "phone_number",
        "register_number",
        "department",
        "branch",
        "college_name",
        "class_10_marks",
        "class_10_board",
        "class_12_marks",
        "class_12_board",
        "degree",
        "cgpa",
        "active_backlogs",
        "backlog_history",
        "year_of_study",
        "batch_year",
        "preferred_roles",
        "preferred_locations",
        "looking_for",
        "remote_preference",
        "open_to_relocation",
        "portfolio_url",
        "linkedin_url",
        "github_url",
        "coding_profile_url",
    ]
    for key in meta_keys:
        if key not in payload:
            continue
        value = payload[key]
        if key in {"preferred_roles", "preferred_locations"}:
            profile_meta[key] = normalize_text_list(value)
        else:
            profile_meta[key] = value

    if profile_meta:
        db_updates["resume_parse_confidence"] = {
            **meta_source,
            "profile_meta": profile_meta,
        }

    if db_updates:
        supabase.table("students").update(db_updates).eq("student_id", student_id).execute()

    clear_profile_dependent_caches()
    return {"message": "Profile updated"}


@router.put("/{student_id}/skills")
def update_profile_skills(student_id: str, data: SkillsUpdate, user=Depends(get_current_user)):
    if current_student_key(user) != student_id:
        raise HTTPException(status_code=403, detail="You can only update your own profile")

    student = load_student_by_student_id(student_id)
    existing_result = supabase.table("skills").select("skill_name, verified").eq("student_id", student_id).execute()
    existing_rows = existing_result.data or []
    verified_by_skill = {str(row.get("skill_name") or "").strip().lower(): bool(row.get("verified")) for row in existing_rows}

    supabase.table("skills").delete().eq("student_id", student_id).execute()

    cleaned = []
    seen = set()
    for skill in data.skills:
        name = str(skill.name).strip()
        if not name:
            continue
        lowered = name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append({
            "student_id": student_id,
            "skill_name": name,
            "proficiency": str(skill.proficiency or "Not set").strip() or "Not set",
            "verified": verified_by_skill.get(lowered, False),
        })

    if cleaned:
        supabase.table("skills").insert(cleaned).execute()

    meta_source = student.get("resume_parse_confidence") or {}
    profile_meta = dict(meta_source.get("profile_meta") or {})
    profile_meta["manual_skills_saved"] = True
    supabase.table("students").update({
        "resume_parse_confidence": {
            **meta_source,
            "profile_meta": profile_meta,
        }
    }).eq("student_id", student_id).execute()

    clear_profile_dependent_caches()
    return {"message": "Skills updated", "count": len(cleaned)}


@router.get("/recruiter/me")
def get_recruiter_profile(user=Depends(get_current_recruiter)):
    recruiter_id = str(user.get("id"))
    meta = recruiter_profile_meta(recruiter_id)
    active_roles = count_rows("jobs", {"recruiter_id": recruiter_id, "is_active": True})

    return {
        "recruiter_id": recruiter_id,
        "identity": {
            "name": user.get("name") or "",
            "email": user.get("email") or "",
            "company_name": user.get("company_name") or "",
            "company_domain": user.get("company_domain") or "",
            "designation": meta.get("designation"),
            "phone_number": meta.get("phone_number"),
        },
        "company": {
            "industry": meta.get("industry"),
            "company_size": meta.get("company_size"),
            "headquarters": meta.get("headquarters"),
            "about_company": meta.get("about_company"),
            "hiring_pitch": meta.get("hiring_pitch"),
        },
        "hiring_preferences": {
            "hiring_type": meta.get("hiring_type"),
            "preferred_departments": normalize_text_list(meta.get("preferred_departments")),
            "preferred_graduation_years": meta.get("preferred_graduation_years") or [],
            "min_cgpa": meta.get("min_cgpa"),
            "max_active_backlogs": meta.get("max_active_backlogs"),
            "work_mode": meta.get("work_mode"),
        },
        "links": {
            "website_url": meta.get("website_url"),
            "careers_url": meta.get("careers_url"),
            "linkedin_url": meta.get("linkedin_url"),
        },
        "activity": {
            "posted_roles": count_rows("jobs", {"recruiter_id": recruiter_id}),
            "active_roles": active_roles,
            "students_interested": recruiter_student_interest_count(recruiter_id),
            "liked_students": count_rows("recruiter_interest", {"recruiter_id": recruiter_id}),
            "matches": count_rows("matches", {"recruiter_id": recruiter_id}),
            "passed_students": count_rows("recruiter_pass", {"recruiter_id": recruiter_id}),
        },
    }


@router.patch("/recruiter/me")
def update_recruiter_profile(data: RecruiterProfileUpdate, user=Depends(get_current_recruiter)):
    recruiter_id = str(user.get("id"))
    payload = data.model_dump(exclude_unset=True)

    db_updates = {
        key: payload[key]
        for key in ("name", "company_name", "company_domain")
        if key in payload and payload[key] is not None
    }
    if db_updates:
        supabase.table("recruiters").update(db_updates).eq("id", recruiter_id).execute()

    profiles = load_recruiter_profiles()
    existing = dict(profiles.get(recruiter_id, {}) or {})
    meta_keys = [
        "designation",
        "phone_number",
        "industry",
        "company_size",
        "headquarters",
        "hiring_type",
        "preferred_departments",
        "preferred_graduation_years",
        "min_cgpa",
        "max_active_backlogs",
        "work_mode",
        "about_company",
        "hiring_pitch",
        "website_url",
        "careers_url",
        "linkedin_url",
    ]
    for key in meta_keys:
        if key not in payload:
            continue
        value = payload[key]
        if key == "preferred_departments":
            existing[key] = normalize_text_list(value)
        else:
            existing[key] = value
    profiles[recruiter_id] = existing
    save_recruiter_profiles(profiles)

    clear_profile_dependent_caches()
    return {"message": "Recruiter profile updated"}
