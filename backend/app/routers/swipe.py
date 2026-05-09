import threading
import time
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.database import supabase
from app.routers.deps import get_current_recruiter, get_current_user
from app.services.talentforge_matcher import all_student_rows, enrich_student_row, is_canonical_job, score_student_for_job

router = APIRouter(tags=["swipe"])
_SUPABASE_LOCK = threading.Lock()


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


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace("{", "").replace("}", "").split(",") if item.strip()]


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


def job_to_card(job: Dict[str, Any], recruiter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        "job_type": rounds[0] if has_talentforge_meta else "",
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
    sid = str(student.get("student_id") or student.get("id") or student.get("register_number"))
    profile = student.get("_talentforge_profile") or {}
    skills = as_list(student.get("skills")) or profile.get("skills") or []
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
        "preference_summary": student.get("email") or student.get("college_name") or "",
        "profile_tags": as_list(student.get("certifications")) + as_list(student.get("projects")),
        "highlight_line": f"Best project: {projects[0]['title']} with practical implementation details.",
        "phi_score": float(student.get("_match_score") or 0.75),
        "match_breakdown": student.get("_match_breakdown") or {},
        "job_id": job_id,
    }


@router.get("/student/feed")
def student_feed(limit: int = Query(default=20, le=50), offset: int = 0, user=Depends(get_current_user)):
    sid = student_id(user)
    liked = {row["job_id"] for row in (execute_supabase(lambda: supabase.table("student_interest").select("job_id").eq("student_id", sid)).data or [])}
    passed = {row["job_id"] for row in (execute_supabase(lambda: supabase.table("student_pass").select("job_id").eq("student_id", sid)).data or [])}
    jobs = execute_supabase(lambda: supabase.table("jobs").select("*").eq("is_active", True)).data or []
    jobs = [job for job in jobs if is_canonical_job(job) or job.get("recruiter_id")]
    visible = [job for job in jobs if job["id"] not in liked and job["id"] not in passed]
    cards = [job_to_card(job, get_recruiter(job.get("recruiter_id"))) for job in visible]
    cards.sort(key=lambda item: (bool(item.get("job_type")), item["phi_score"]), reverse=True)
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


@router.get("/recruiter/feed")
def recruiter_feed(job_id: Optional[str] = None, limit: int = Query(default=20, le=50), offset: int = 0, user=Depends(get_current_recruiter)):
    if not job_id:
        jobs = execute_supabase(lambda: supabase.table("jobs").select("*").eq("recruiter_id", user["id"]).limit(1)).data or []
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
    students = list(students_by_id.values())
    visible = [row for row in students if student_id(row) not in liked and student_id(row) not in passed]
    scored = []
    for row in visible:
        enriched = enrich_student_row(row)
        score, breakdown = score_student_for_job(enriched, job, interested_rank)
        enriched["_match_score"] = score
        enriched["_match_breakdown"] = breakdown
        scored.append(enriched)
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
