import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.database import supabase
from app.routers.deps import get_current_recruiter, get_current_user
from app.services.bias_reduction import load_variant_artifact, score_variant_probabilities
from app.services.talentforge_matcher import all_student_rows, enrich_student_row, is_canonical_job, score_student_for_job
from src.explainability.criteria_checker import check_criteria
from src.model.inference import build_inference_features

router = APIRouter(tags=["swipe"])
_SUPABASE_LOCK = threading.Lock()
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FAIRNESS_BLEND_TALENTFORGE_WEIGHT = 0.6
FAIRNESS_BLEND_MODEL_WEIGHT = 0.4
PROJECT_COMPLEXITY_MAP = {"Basic": 1, "Intermediate": 2, "Advanced": 3}
CERT_TIER_MAP = {"Local": 1, "National": 2, "Global_Standard": 3, "Global_Premium": 4}
INTERNSHIP_TIER_MAP = {"NGO": 1, "Startup": 2, "Tier3": 3, "Tier2": 4, "Tier1": 5}


class JobSwipeRequest(BaseModel):
    job_id: str


class RecruiterSwipeRequest(BaseModel):
    student_id: str
    job_id: str


class RecruiterPassRequest(BaseModel):
    student_id: str


class RecruiterJobCreate(BaseModel):
    role_title: str
    industry: str = ""
    location: str = ""
    remote_policy: str = "hybrid"
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    interview_timeline: str = ""
    mentorship: str = ""
    highlight_line: str = ""
    min_cgpa: float = 0
    allowed_departments: List[str] = []
    grad_years_eligible: List[int] = []


class RecruiterJobUpdate(RecruiterJobCreate):
    is_active: bool = True


class RecruiterJobStatusUpdate(BaseModel):
    is_active: bool


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace("{", "").replace("}", "").split(",") if item.strip()]


def normalize_track(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "intern" in text:
        return "internship"
    if "full" in text:
        return "full-time"
    return ""


def infer_track_from_job(job: Dict[str, Any]) -> str:
    texts = [
        job.get("job_type"),
        " ".join(as_list(job.get("selection_rounds"))),
        job.get("role_title"),
        job.get("role"),
        job.get("highlight_line"),
        job.get("job_description"),
        job.get("ctc"),
    ]
    combined = " ".join(str(value or "") for value in texts).lower()
    if "intern" in combined or "/ month" in combined or "per month" in combined:
        return "internship"
    if "full-time" in combined or "/ year" in combined or "per year" in combined:
        return "full-time"
    return "full-time"


def infer_student_track(student: Dict[str, Any]) -> str:
    explicit = normalize_track(
        student.get("preferred_job_type")
        or student.get("_preferred_job_type")
        or student.get("preference_summary")
        or student.get("college_name")
    )
    if explicit:
        return explicit

    year_of_study = safe_int(student.get("year_of_study"))
    batch_year = safe_int(student.get("batch_year"))
    if year_of_study >= 4:
        return "full-time"
    if year_of_study:
        return "internship"
    if batch_year:
        return "full-time" if batch_year <= 2025 else "internship"
    return "internship"


def execute_supabase(build_query: Callable[[], Any], retries: int = 3):
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with _SUPABASE_LOCK:
                return build_query().execute()
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.2 * (attempt + 1))
    raise last_error or RuntimeError("Supabase request failed")


def student_id(user: Dict[str, Any]) -> str:
    return str(user.get("student_id") or user.get("id") or user.get("register_number"))


def as_text_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [value]
    texts = []
    for item in items:
        if isinstance(item, dict):
            parts = [str(item.get(key) or "").strip() for key in ("title", "description", "tech_stack", "domain", "name") if item.get(key)]
            text = " ".join(part for part in parts if part)
        else:
            text = str(item).strip()
        if text:
            texts.append(text)
    return texts


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def first_present(record: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def merge_unique_texts(*sources: Any, limit: int = 8) -> List[str]:
    seen = set()
    merged: List[str] = []
    for source in sources:
        for item in as_text_list(source):
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


def canonicalize_job_record(job: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(job)
    normalized["company_name"] = first_present(normalized, "company_name", default="Company")
    normalized["role_title"] = first_present(normalized, "role_title", "role", "role_offered", default="Role")
    normalized["role"] = first_present(normalized, "role", "role_title", "role_offered", default=normalized["role_title"])
    normalized["required_skills"] = merge_unique_texts(normalized.get("required_skills"), limit=16)
    normalized["preferred_skills"] = merge_unique_texts(normalized.get("preferred_skills"), limit=16)
    normalized["allowed_departments"] = ",".join(as_list(normalized.get("allowed_departments") or normalized.get("allowed_branches")))
    normalized["max_active_backlogs"] = safe_int(first_present(normalized, "max_active_backlogs", "max_backlogs"), 0)
    normalized["job_type"] = "Internship" if infer_track_from_job(normalized) == "internship" else "Full-time"
    normalized["selection_rounds"] = as_list(normalized.get("selection_rounds"))
    if not normalized["selection_rounds"]:
        normalized["selection_rounds"] = [normalized["job_type"]]
    return normalized


@lru_cache(maxsize=1)
def load_student_csv_rows() -> Dict[str, Dict[str, Any]]:
    path = DATA_DIR / "students.csv"
    if not path.exists():
        return {}
    frame = pd.read_csv(path).fillna("")
    return {str(row["student_id"]): row for row in frame.to_dict("records") if row.get("student_id")}


@lru_cache(maxsize=1)
def load_student_feature_rows() -> Dict[str, Dict[str, Any]]:
    path = DATA_DIR / "student_features.csv"
    if not path.exists():
        return {}
    frame = pd.read_csv(path).fillna("")
    return {str(row["student_id"]): row for row in frame.to_dict("records") if row.get("student_id")}


@lru_cache(maxsize=1)
def load_fairlearn_artifact() -> Optional[Dict[str, Any]]:
    try:
        return load_variant_artifact("champion")
    except Exception:
        return None


def normalize_job_for_rules_and_model(job: Dict[str, Any]) -> Dict[str, Any]:
    normalized = canonicalize_job_record(job)
    normalized["required_skills"] = ",".join(as_list(normalized.get("required_skills")))
    normalized["preferred_skills"] = ",".join(as_list(normalized.get("preferred_skills")))
    return normalized


def build_student_model_input(student: Dict[str, Any]) -> Dict[str, Any]:
    sid = student_id(student)
    base_row = load_student_csv_rows().get(sid, {})
    feature_row = load_student_feature_rows().get(sid, {})
    profile = student.get("_talentforge_profile") or {}
    projects = profile.get("projects") or student.get("projects") or []
    certifications = profile.get("certifications") or student.get("certifications") or []
    internships = profile.get("internships") or student.get("internships") or []
    skills = merge_unique_texts(profile.get("skills"), student.get("skills"), feature_row.get("skill_list"), limit=16)

    merged = {**base_row, **feature_row, **profile, **student}
    merged["student_id"] = sid
    merged["full_name"] = first_present(merged, "full_name", "name", default=sid)
    merged["department"] = first_present(merged, "department", "branch", default="")
    merged["cgpa"] = safe_float(merged.get("cgpa"))
    merged["10th_marks"] = safe_float(first_present(merged, "10th_marks", "tenth_marks"))
    merged["12th_marks"] = safe_float(first_present(merged, "12th_marks", "twelfth_marks"))
    merged["cgpa_normalized"] = safe_float(merged.get("cgpa_normalized"), merged["cgpa"] / 10 if merged["cgpa"] else 0.0)
    merged["10th_normalized"] = safe_float(merged.get("10th_normalized"), merged["10th_marks"] / 100 if merged["10th_marks"] else 0.0)
    merged["12th_normalized"] = safe_float(merged.get("12th_normalized"), merged["12th_marks"] / 100 if merged["12th_marks"] else 0.0)
    merged["active_backlogs"] = safe_int(first_present(merged, "active_backlogs", "backlogs"))
    merged["num_projects"] = safe_int(merged.get("num_projects"), len(projects))
    merged["num_papers"] = safe_int(merged.get("num_papers"))
    merged["max_paper_tier"] = safe_int(merged.get("max_paper_tier"))
    merged["num_advanced_skills"] = safe_int(merged.get("num_advanced_skills"))
    merged["num_verified_skills"] = safe_int(merged.get("num_verified_skills"))
    merged["num_global_premium"] = safe_int(merged.get("num_global_premium"))
    merged["num_global_standard"] = safe_int(merged.get("num_global_standard"))
    merged["num_national"] = safe_int(merged.get("num_national"))
    merged["max_cert_tier"] = safe_int(
        merged.get("max_cert_tier"),
        max((CERT_TIER_MAP.get(str(item.get("tier") or "").strip(), 0) for item in certifications if isinstance(item, dict)), default=0),
    )
    merged["max_project_complexity"] = safe_int(
        merged.get("max_project_complexity"),
        max((PROJECT_COMPLEXITY_MAP.get(str(item.get("complexity") or "").strip(), 0) for item in projects if isinstance(item, dict)), default=0),
    )
    merged["total_internship_months"] = safe_float(
        merged.get("total_internship_months"),
        sum(safe_float(item.get("duration_months")) for item in internships if isinstance(item, dict)),
    )
    merged["max_internship_tier"] = safe_int(
        merged.get("max_internship_tier"),
        max((INTERNSHIP_TIER_MAP.get(str(item.get("company_tier") or "").strip(), 0) for item in internships if isinstance(item, dict)), default=0),
    )
    merged["skill_list"] = skills
    merged["skills"] = skills
    merged["projects"] = as_text_list(projects)
    merged["preferred_job_type"] = infer_student_track(merged)
    merged["_preferred_job_type"] = merged["preferred_job_type"]
    merged["preferred_role"] = first_present(merged, "preferred_role", default=first_present(merged, "department", "branch", default="Generalist"))
    merged["preferred_location"] = first_present(merged, "preferred_job_location", "location", default="India")
    merged["preferred_company_size"] = first_present(merged, "preferred_job_size", default="Any company")
    merged["preference_summary"] = (
        first_present(merged, "preference_summary", "college_name")
        or f"Prefers {merged['preferred_job_type']} roles in {merged['preferred_location']} as {merged['preferred_role']}."
    )
    return merged


def refresh_scorecard_summary(scorecard: Dict[str, Any]) -> Dict[str, Any]:
    hard_failures = [
        key for key, value in scorecard.items()
        if key != "_summary" and value.get("is_hard") and not value.get("passed")
    ]
    soft_weaknesses = [
        key for key, value in scorecard.items()
        if key != "_summary" and not value.get("is_hard") and not value.get("passed", True)
    ]
    hard_checks = [value for key, value in scorecard.items() if key != "_summary" and value.get("is_hard")]
    soft_checks = [value for key, value in scorecard.items() if key != "_summary" and not value.get("is_hard")]
    soft_score = sum(1 for value in soft_checks if value.get("passed", True)) / len(soft_checks) if soft_checks else 1.0
    scorecard["_summary"] = {
        "hard_pass": all(value.get("passed") for value in hard_checks),
        "soft_score": soft_score,
        "eligible": all(value.get("passed") for value in hard_checks) and soft_score >= 0.4,
        "hard_failures": hard_failures,
        "soft_weaknesses": soft_weaknesses,
    }
    return scorecard


def passes_hard_criteria(student: Dict[str, Any], job: Dict[str, Any]) -> bool:
    normalized_job = normalize_job_for_rules_and_model(job)
    student_input = build_student_model_input(student)
    scorecard = check_criteria(student_input, normalized_job, student_skills=student_input.get("skill_list", []))

    if not as_list(job.get("allowed_departments") or job.get("allowed_branches")):
        scorecard["department_check"]["passed"] = True
        scorecard["department_check"]["required_value"] = "Any"
        scorecard["department_check"]["message"] = "No department restriction for this job"
        refresh_scorecard_summary(scorecard)

    return bool(scorecard.get("_summary", {}).get("hard_pass"))


def fairlearn_score_for_pair(student: Dict[str, Any], job: Dict[str, Any]) -> Optional[float]:
    artifact = load_fairlearn_artifact()
    if not artifact:
        return None

    student_input = build_student_model_input(student)
    pair_features = build_inference_features(student_input, normalize_job_for_rules_and_model(job))
    feature_frame = pd.DataFrame([pair_features]).reindex(columns=artifact["feature_cols"], fill_value=0)
    probabilities = score_variant_probabilities(
        artifact["model"],
        artifact["scaler"].transform(feature_frame.fillna(0)),
    )
    if len(probabilities) == 0:
        return None
    return float(probabilities[0])


def blended_pair_score(student: Dict[str, Any], job: Dict[str, Any], interested_rank: Optional[Dict[str, int]] = None) -> tuple[float, Dict[str, float]]:
    talentforge_score, breakdown = score_student_for_job(student, job, interested_rank or {})
    fairlearn_score = fairlearn_score_for_pair(student, job)
    final_score = talentforge_score
    if fairlearn_score is not None:
        final_score = (
            (FAIRNESS_BLEND_TALENTFORGE_WEIGHT * talentforge_score) +
            (FAIRNESS_BLEND_MODEL_WEIGHT * fairlearn_score)
        )
        breakdown["fairlearn"] = round(fairlearn_score, 3)
        breakdown["talentforge"] = round(talentforge_score, 3)
        breakdown["overall"] = round(final_score, 3)
    return final_score, breakdown


def sort_jobs_for_student(student: Dict[str, Any], jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored_jobs = []
    for job in jobs:
        score, breakdown = blended_pair_score(student, job)
        scored_jobs.append({**job, "phi_score": score, "_match_breakdown": breakdown})
    scored_jobs.sort(key=lambda item: (bool(item.get("job_type")), float(item.get("phi_score") or 0)), reverse=True)
    return scored_jobs


def job_track(job: Dict[str, Any]) -> str:
    return infer_track_from_job(canonicalize_job_record(job))


def student_preference_track(student: Dict[str, Any]) -> str:
    return infer_student_track(student)


def load_current_student(sid: str, user: Dict[str, Any]) -> Dict[str, Any]:
    merged = {}
    for row in all_student_rows():
        if student_id(row) == sid:
            merged = {**merged, **row}
            break
    result = execute_supabase(lambda: supabase.table("students").select("*").eq("student_id", sid).maybe_single())
    if result and result.data:
        merged = {**merged, **result.data}
    elif user.get("id") and user.get("id") != sid:
        fallback = execute_supabase(lambda: supabase.table("students").select("*").eq("id", user["id"]).maybe_single())
        if fallback and fallback.data:
            merged = {**merged, **fallback.data}
    return {**merged, **user, "student_id": sid}


def job_to_card(job: Dict[str, Any], recruiter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    job = canonicalize_job_record(job)
    company_name = (recruiter or {}).get("company_name") or job.get("company_name") or "Company"
    role_title = job.get("role_title") or job.get("role") or "Intern"
    rounds = as_list(job.get("selection_rounds"))
    has_talentforge_meta = bool(rounds and rounds[0] in {"Full-time", "Internship"})
    return {
        "id": job["id"],
        "recruiter_id": job.get("recruiter_id"),
        "company_name": company_name,
        "role_title": role_title,
        "industry": job.get("industry") or "Technology",
        "location": job.get("location") or "Chennai",
        "remote_policy": job.get("remote_policy") or "hybrid",
        "required_skills": as_list(job.get("required_skills")),
        "preferred_skills": as_list(job.get("preferred_skills")),
        "interview_timeline": job.get("interview_timeline") or "OA -> 2 technical rounds -> offer, ~3 weeks",
        "mentorship": job.get("mentorship") or "Interns work with a mentor and get weekly project feedback.",
        "highlight_line": job.get("highlight_line") or job.get("job_description") or "Build production features with a small, focused team.",
        "careers_url": job.get("careers_url") or "",
        "salary": job.get("ctc") or (f"{job.get('package_lpa')} LPA" if job.get("package_lpa") else ""),
        "company_size": rounds[1] if has_talentforge_meta and len(rounds) > 1 else "",
        "candidate_level": rounds[2] if has_talentforge_meta and len(rounds) > 2 else "",
        "job_type": rounds[0] if has_talentforge_meta else (job.get("job_type") or ""),
        "phi_score": float(job.get("phi_score") or 0.75),  # TODO: replace with recommender per-pair score.
    }


def get_job(job_id: str) -> Dict[str, Any]:
    result = execute_supabase(lambda: supabase.table("jobs").select("*").eq("id", job_id).maybe_single())
    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return result.data


def get_recruiter(recruiter_id: str) -> Optional[Dict[str, Any]]:
    if not recruiter_id:
        return None
    result = execute_supabase(lambda: supabase.table("recruiters").select("*").eq("id", recruiter_id).maybe_single())
    return result.data if result else None


def has_row(table: str, filters: Dict[str, Any]) -> bool:
    query = supabase.table(table).select("id")
    for key, value in filters.items():
        query = query.eq(key, value)
    result = execute_supabase(lambda: query.maybe_single())
    return bool(result and result.data)


def insert_if_missing(table: str, payload: Dict[str, Any], unique_filters: Dict[str, Any]) -> None:
    if has_row(table, unique_filters):
        return
    execute_supabase(lambda: supabase.table(table).insert(payload))


def create_match_if_ready(student: str, recruiter_id: str, job_id: str) -> bool:
    if not has_row("student_interest", {"student_id": student, "job_id": job_id}):
        return False
    if not has_row("recruiter_interest", {"student_id": student, "job_id": job_id, "recruiter_id": recruiter_id}):
        return False
    insert_if_missing(
        "matches",
        {"student_id": student, "recruiter_id": recruiter_id, "job_id": job_id},
        {"student_id": student, "job_id": job_id},
    )
    # TODO: persist notifications once a notifications table exists.
    return True


def student_to_card(student: Dict[str, Any], job_id: Optional[str] = None, hydrate_details: bool = True) -> Dict[str, Any]:
    student = build_student_model_input(student)
    sid = str(student.get("student_id") or student.get("id") or student.get("register_number"))
    profile = student.get("_talentforge_profile") or {}
    skills = merge_unique_texts(student.get("skills"), profile.get("skills"), limit=8)
    projects = [{"title": "Applied project", "description": "Built a practical project aligned with industry requirements."}]
    certs = []
    if hydrate_details:
        skills_result = execute_supabase(lambda: supabase.table("skills").select("*").eq("student_id", sid))
        projects_result = execute_supabase(lambda: supabase.table("projects").select("*").eq("student_id", sid).limit(2))
        certs_result = execute_supabase(lambda: supabase.table("certifications").select("*").eq("student_id", sid).limit(3))
        skills = [item.get("skill_name") for item in (skills_result.data or []) if item.get("skill_name")] or skills
        projects = [
            {
                "title": item.get("project_title") or "Project",
                "description": item.get("domain") or item.get("tech_stack") or "Applied technical project with measurable outcomes.",
            }
            for item in (projects_result.data or [])
        ] or projects
        certs = [
            {"name": item.get("cert_name") or "Certification", "issuer": item.get("issuing_body") or "Issuer"}
            for item in (certs_result.data or [])
        ]
    else:
        projects = profile.get("projects") or projects
        certs = profile.get("certifications") or certs
    grad_year = int(student.get("batch_year") or (2024 + int(student.get("year_of_study") or 3)))
    return {
        "student_id": sid,
        "email": student.get("email") or "",
        "full_name": student.get("full_name") or student.get("name") or sid,
        "department": student.get("department") or student.get("branch") or "CSE",
        "degree": "B.Tech",
        "university": "SRM Institute of Science and Technology",
        "graduation_year": grad_year,
        "cgpa": float(student.get("cgpa") or 0),
        "skills": skills[:8],
        "top_projects": projects,
        "coursework": ["Data Structures", "DBMS", "Operating Systems", "Machine Learning"],
        "certifications": [
            {"name": item.get("name") or item.get("cert_name") or "Certification", "issuer": item.get("issuer") or item.get("issuing_body") or "Issuer"}
            for item in certs
        ],
        "availability": "Summer internship window",
        "work_authorization": "India",
        "portfolio_url": student.get("portfolio_url") or "",
        "preference_summary": student.get("preference_summary") or student.get("email") or student.get("college_name") or "",
        "profile_tags": as_list(student.get("certifications")) + as_list(student.get("projects")),
        "highlight_line": f"Best project: {projects[0]['title']} with practical implementation details.",
        "phi_score": float(student.get("_match_score") or 0.75),
        "match_breakdown": student.get("_match_breakdown") or {},
        "job_id": job_id,
    }


@router.get("/student/feed")
def student_feed(
    job_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=50),
    offset: int = 0,
    user=Depends(get_current_user),
):
    sid = student_id(user)
    liked = {row["job_id"] for row in (execute_supabase(lambda: supabase.table("student_interest").select("job_id").eq("student_id", sid)).data or [])}
    passed = {row["job_id"] for row in (execute_supabase(lambda: supabase.table("student_pass").select("job_id").eq("student_id", sid)).data or [])}
    all_jobs = execute_supabase(lambda: supabase.table("jobs").select("*").eq("is_active", True)).data or []
    jobs = [job for job in all_jobs if is_canonical_job(job) or job.get("recruiter_id")]
    requested_track = normalize_track(job_type)
    if requested_track:
        all_jobs = [job for job in all_jobs if job_track(job) == requested_track]
        jobs = [job for job in jobs if job_track(job) == requested_track]
    student = enrich_student_row(build_student_model_input(load_current_student(sid, user)))
    unseen_jobs = [job for job in jobs if job["id"] not in liked and job["id"] not in passed]
    primary_jobs = [
        job for job in unseen_jobs
        if passes_hard_criteria(student, job)
    ]
    all_unseen_jobs = [job for job in all_jobs if job["id"] not in liked and job["id"] not in passed]
    fallback_jobs = [
        job for job in all_unseen_jobs
        if job["id"] not in {item["id"] for item in primary_jobs}
    ]
    ranked_jobs = sort_jobs_for_student(student, primary_jobs) + sort_jobs_for_student(student, fallback_jobs)
    cards = [job_to_card(job, get_recruiter(job.get("recruiter_id"))) for job in ranked_jobs]
    return {"jobs": cards[offset:offset + limit]}


@router.get("/student/interested")
def student_interested(user=Depends(get_current_user)):
    sid = student_id(user)
    responded = {row["job_id"] for row in (execute_supabase(lambda: supabase.table("student_interest").select("job_id").eq("student_id", sid)).data or [])}
    passed = {row["job_id"] for row in (execute_supabase(lambda: supabase.table("student_pass").select("job_id").eq("student_id", sid)).data or [])}
    matches = {row["job_id"] for row in (execute_supabase(lambda: supabase.table("matches").select("job_id").eq("student_id", sid)).data or [])}
    rows = execute_supabase(lambda: supabase.table("recruiter_interest").select("*").eq("student_id", sid)).data or []
    cards = []
    for row in rows:
        if row["job_id"] in responded or row["job_id"] in passed or row["job_id"] in matches:
            continue
        job = get_job(row["job_id"])
        cards.append(job_to_card(job, get_recruiter(row["recruiter_id"])))
    return {"jobs": cards}


@router.get("/student/matches")
def student_matches(user=Depends(get_current_user)):
    sid = student_id(user)
    rows = execute_supabase(lambda: supabase.table("matches").select("*").eq("student_id", sid)).data or []
    matches = []
    for row in rows:
        job = get_job(row["job_id"])
        recruiter = get_recruiter(row["recruiter_id"]) or {}
        matches.append({**row, "company_name": recruiter.get("company_name") or "Company", "role_title": job.get("role_title") or job.get("role") or "Role"})
    return {"matches": matches}


@router.post("/student/swipe/right")
def student_swipe_right(req: JobSwipeRequest, user=Depends(get_current_user)):
    sid = student_id(user)
    job = get_job(req.job_id)
    recruiter_id = job.get("recruiter_id")
    insert_if_missing("student_interest", {"student_id": sid, "job_id": req.job_id}, {"student_id": sid, "job_id": req.job_id})
    matched = create_match_if_ready(sid, recruiter_id, req.job_id) if recruiter_id else False
    return {"matched": matched}


@router.post("/student/swipe/left")
def student_swipe_left(req: JobSwipeRequest, user=Depends(get_current_user)):
    sid = student_id(user)
    insert_if_missing("student_pass", {"student_id": sid, "job_id": req.job_id}, {"student_id": sid, "job_id": req.job_id})
    return {"passed": True}


@router.get("/recruiter/jobs")
def recruiter_jobs(user=Depends(get_current_recruiter)):
    rows = execute_supabase(lambda: supabase.table("jobs").select("*").eq("recruiter_id", user["id"])).data or []
    canonical_rows = [row for row in rows if is_canonical_job(row)]
    if canonical_rows:
        rows = canonical_rows
    return {"jobs": [job_to_card(row, user) for row in rows]}


@router.post("/recruiter/jobs")
def recruiter_create_job(req: RecruiterJobCreate, user=Depends(get_current_recruiter)):
    payload = req.model_dump()
    payload["recruiter_id"] = user["id"]
    result = execute_supabase(lambda: supabase.table("jobs").insert(payload))
    created = result.data[0] if result and result.data else payload
    return job_to_card(created, user)


@router.put("/recruiter/jobs/{job_id}")
def recruiter_update_job(job_id: str, req: RecruiterJobUpdate, user=Depends(get_current_recruiter)):
    existing = execute_supabase(lambda: supabase.table("jobs").select("*").eq("id", job_id).eq("recruiter_id", user["id"]).limit(1))
    row = existing.data[0] if existing and existing.data else None
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    payload = req.model_dump()
    result = execute_supabase(lambda: supabase.table("jobs").update(payload).eq("id", job_id).eq("recruiter_id", user["id"]).select("*"))
    updated = result.data[0] if result and result.data else {**row, **payload, "id": job_id}
    return job_to_card(updated, user)


@router.patch("/recruiter/jobs/{job_id}/status")
def recruiter_update_job_status(job_id: str, is_active: bool, user=Depends(get_current_recruiter)):
    existing = execute_supabase(lambda: supabase.table("jobs").select("*").eq("id", job_id).eq("recruiter_id", user["id"]).limit(1))
    row = existing.data[0] if existing and existing.data else None
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    result = execute_supabase(
        lambda: supabase.table("jobs").update({"is_active": is_active}).eq("id", job_id).eq("recruiter_id", user["id"]).select("*")
    )
    updated = result.data[0] if result and result.data else {**row, "is_active": is_active}
    return job_to_card(updated, user)


@router.post("/recruiter/jobs/{job_id}/status")
def recruiter_update_job_status_post(job_id: str, req: RecruiterJobStatusUpdate, user=Depends(get_current_recruiter)):
    return recruiter_update_job_status(job_id, req.is_active, user)


@router.delete("/recruiter/jobs/{job_id}")
def recruiter_delete_job(job_id: str, user=Depends(get_current_recruiter)):
    existing = execute_supabase(lambda: supabase.table("jobs").select("id").eq("id", job_id).eq("recruiter_id", user["id"]).limit(1))
    row = existing.data[0] if existing and existing.data else None
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    execute_supabase(lambda: supabase.table("jobs").delete().eq("id", job_id).eq("recruiter_id", user["id"]))
    return {"deleted": True, "job_id": job_id}


@router.post("/recruiter/jobs/{job_id}/delete")
def recruiter_delete_job_post(job_id: str, user=Depends(get_current_recruiter)):
    return recruiter_delete_job(job_id, user)


@router.get("/recruiter/feed")
def recruiter_feed_with_track(
    job_id: Optional[str] = None,
    preference_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=50),
    offset: int = 0,
    user=Depends(get_current_recruiter),
):
    requested_track = normalize_track(preference_type)
    if not job_id:
        jobs = execute_supabase(lambda: supabase.table("jobs").select("*").eq("recruiter_id", user["id"])).data or []
        jobs = [job for job in jobs if job.get("is_active", True)]
        if requested_track:
            jobs = [job for job in jobs if job_track(job) == requested_track]
        if not jobs:
            return {"students": []}
        job_id = jobs[0]["id"]
        job = jobs[0]
    else:
        job = get_job(job_id)
    liked = {row["student_id"] for row in (execute_supabase(lambda: supabase.table("recruiter_interest").select("student_id").eq("recruiter_id", user["id"]).eq("job_id", job_id)).data or [])}
    passed = {row["student_id"] for row in (execute_supabase(lambda: supabase.table("recruiter_pass").select("student_id").eq("recruiter_id", user["id"])).data or [])}
    interested = [
        row["student_id"]
        for row in (execute_supabase(lambda: supabase.table("student_interest").select("student_id").eq("job_id", job_id)).data or [])
        if row.get("student_id")
    ]
    interested_rank = {sid: index for index, sid in enumerate(interested)}
    supabase_students = execute_supabase(lambda: supabase.table("students").select("*")).data or []
    students_by_id = {
        student_id(row): row
        for row in all_student_rows()
    }
    for row in supabase_students:
        sid = student_id(row)
        students_by_id[sid] = {**students_by_id.get(sid, {}), **row}
    students = [build_student_model_input(row) for row in students_by_id.values()]
    unseen_students = [
        row for row in students
        if student_id(row) not in liked and student_id(row) not in passed
    ]
    if requested_track:
        matched_track_students = [row for row in unseen_students if student_preference_track(row) == requested_track]
        other_students = [row for row in unseen_students if student_preference_track(row) != requested_track]
        unseen_students = matched_track_students + other_students
    primary_students = [row for row in unseen_students if passes_hard_criteria(row, job)]
    primary_ids = {student_id(row) for row in primary_students}
    fallback_students = [row for row in unseen_students if student_id(row) not in primary_ids]

    def score_student_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scored_rows = []
        for row in rows:
            enriched = enrich_student_row(row)
            final_score, breakdown = blended_pair_score(enriched, job, interested_rank)
            enriched["_match_score"] = final_score
            enriched["_match_breakdown"] = breakdown
            scored_rows.append(enriched)
        return scored_rows

    scored = score_student_rows(primary_students) + score_student_rows(fallback_students)
    scored.sort(key=lambda row: (
        student_id(row) not in interested_rank,
        interested_rank.get(student_id(row), 999999),
        -float(row.get("_match_score") or 0),
        str(row.get("email") or ""),
    ))
    page = scored[offset:offset + limit]
    cards = [student_to_card(row, job_id, hydrate_details=False) for row in page]
    return {"students": cards}


@router.get("/recruiter/interested")
def recruiter_interested(user=Depends(get_current_recruiter)):
    rows = execute_supabase(lambda: supabase.table("recruiter_interest").select("*").eq("recruiter_id", user["id"])).data or []
    cards = []
    for row in rows:
        if has_row("matches", {"student_id": row["student_id"], "job_id": row["job_id"]}):
            continue
        result = execute_supabase(lambda: supabase.table("students").select("*").eq("student_id", row["student_id"]).maybe_single())
        if result and result.data:
            cards.append(student_to_card(result.data, row["job_id"]))
    return {"students": cards}


@router.get("/recruiter/matches")
def recruiter_matches(user=Depends(get_current_recruiter)):
    rows = execute_supabase(lambda: supabase.table("matches").select("*").eq("recruiter_id", user["id"])).data or []
    matches = []
    for row in rows:
        job = get_job(row["job_id"])
        student_result = execute_supabase(lambda: supabase.table("students").select("*").eq("student_id", row["student_id"]).maybe_single())
        student = student_result.data if student_result else {}
        matches.append({
            **row,
            "student_name": student.get("full_name") or student.get("name") or row["student_id"],
            "department": student.get("department") or student.get("branch") or "",
            "cgpa": student.get("cgpa"),
            "role_title": job.get("role_title") or job.get("role") or "Role",
        })
    return {"matches": matches}


@router.post("/recruiter/swipe/right")
def recruiter_swipe_right(req: RecruiterSwipeRequest, user=Depends(get_current_recruiter)):
    insert_if_missing(
        "recruiter_interest",
        {"recruiter_id": user["id"], "student_id": req.student_id, "job_id": req.job_id},
        {"recruiter_id": user["id"], "student_id": req.student_id, "job_id": req.job_id},
    )
    matched = create_match_if_ready(req.student_id, user["id"], req.job_id)
    return {"matched": matched}


@router.post("/recruiter/swipe/left")
def recruiter_swipe_left(req: RecruiterPassRequest, user=Depends(get_current_recruiter)):
    insert_if_missing(
        "recruiter_pass",
        {"recruiter_id": user["id"], "student_id": req.student_id},
        {"recruiter_id": user["id"], "student_id": req.student_id},
    )
    return {"passed": True}
