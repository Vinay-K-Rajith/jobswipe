import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

WEIGHTS = {
    "skills": 0.5,
    "role": 0.6,
    "location": 0.2,
    "size": 0.1,
    "category": 0.3,
}


def _read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).lower().replace(",", " ").replace("_", " ").strip()


def _tokens(value: Any) -> List[str]:
    return [token for token in re.split(r"[^a-z0-9+#.]+", _clean(value)) if token]


def _text_similarity(left: str, right: str) -> float:
    left = _clean(left)
    right = _clean(right)
    if not left or not right:
        return 0.0
    try:
        vectors = TfidfVectorizer().fit_transform([left, right])
        return float(cosine_similarity(vectors[0], vectors[1])[0][0])
    except ValueError:
        return 0.0


def _overlap_score(student_values: Iterable[str], required: Iterable[str], preferred: Iterable[str]) -> float:
    student = {token for value in student_values for token in _tokens(value)}
    req = {token for value in required for token in _tokens(value)}
    pref = {token for value in preferred for token in _tokens(value)}
    req_score = len(student & req) / len(req) if req else 1.0
    pref_score = len(student & pref) / len(pref) if pref else 1.0
    return (req_score * 0.7) + (pref_score * 0.3)


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace("{", "").replace("}", "").split(",") if item.strip()]


@lru_cache(maxsize=1)
def canonical_company_keys() -> set[Tuple[str, str]]:
    companies = _read_csv("companies.csv")
    if companies.empty:
        return set()
    companies = companies[companies["company_id"].astype(str).str.startswith("CO")].copy()
    keys = set()
    for _, row in companies.iterrows():
        keys.add((_clean(row.get("company_name")), _clean(row.get("role_offered"))))
    return keys


def is_canonical_job(job: Dict[str, Any]) -> bool:
    keys = canonical_company_keys()
    if not keys:
        return True
    company = _clean(job.get("company_name"))
    role = _clean(job.get("role_title") or job.get("role") or job.get("role_offered"))
    return (company, role) in keys


@lru_cache(maxsize=1)
def load_profiles() -> Dict[str, Dict[str, Any]]:
    students = _read_csv("students.csv")
    skills = _read_csv("skills.csv")
    projects = _read_csv("projects.csv")
    certs = _read_csv("certifications.csv")
    internships = _read_csv("internships.csv")

    profiles: Dict[str, Dict[str, Any]] = {}
    if students.empty:
        return profiles

    students = students[students["student_id"].astype(str).str.startswith("S")].copy()
    allowed_student_ids = set(students["student_id"].astype(str))

    for _, row in students.iterrows():
        sid = str(row.get("student_id"))
        profiles[sid] = {
            "student_id": sid,
            "full_name": row.get("full_name") or sid,
            "department": row.get("department") or "",
            "cgpa": float(row.get("cgpa") or 0),
            "active_backlogs": int(row.get("active_backlogs") or 0),
            "year_of_study": int(row.get("year_of_study") or 3),
            "skills": [],
            "projects": [],
            "certifications": [],
            "internships": [],
        }

    if not skills.empty:
        skills = skills[skills["student_id"].astype(str).isin(allowed_student_ids)].copy()
        for sid, group in skills.groupby("student_id"):
            if sid in profiles:
                profiles[sid]["skills"] = group["skill_name"].dropna().astype(str).tolist()

    if not projects.empty:
        projects = projects[projects["student_id"].astype(str).isin(allowed_student_ids)].copy()
        for sid, group in projects.groupby("student_id"):
            if sid in profiles:
                profiles[sid]["projects"] = [
                    {
                        "title": item.get("project_title") or "Project",
                        "description": item.get("domain") or item.get("tech_stack") or "Applied project",
                        "tech_stack": item.get("tech_stack") or "",
                        "complexity": item.get("complexity") or "",
                    }
                    for item in group.head(3).to_dict("records")
                ]

    if not certs.empty:
        certs = certs[certs["student_id"].astype(str).isin(allowed_student_ids)].copy()
        for sid, group in certs.groupby("student_id"):
            if sid in profiles:
                profiles[sid]["certifications"] = [
                    {
                        "name": item.get("cert_name") or "Certification",
                        "issuer": item.get("issuing_body") or "Issuer",
                        "domain": item.get("domain") or "",
                        "tier": item.get("tier") or "",
                    }
                    for item in group.head(3).to_dict("records")
                ]

    if not internships.empty:
        internships = internships[internships["student_id"].astype(str).isin(allowed_student_ids)].copy()
        for sid, group in internships.groupby("student_id"):
            if sid in profiles:
                profiles[sid]["internships"] = group.to_dict("records")

    return profiles


def all_student_rows() -> List[Dict[str, Any]]:
    rows = []
    for profile in load_profiles().values():
        rows.append({
            "student_id": profile.get("student_id"),
            "full_name": profile.get("full_name"),
            "department": profile.get("department"),
            "cgpa": profile.get("cgpa"),
            "active_backlogs": profile.get("active_backlogs"),
            "year_of_study": profile.get("year_of_study"),
            "skills": profile.get("skills") or [],
            "_talentforge_profile": profile,
        })
    return rows


def profile_for_student(student_id: str) -> Dict[str, Any]:
    return load_profiles().get(str(student_id), {})


def score_student_for_job(student: Dict[str, Any], job: Dict[str, Any], interested_rank: Dict[str, int]) -> Tuple[float, Dict[str, float]]:
    sid = str(student.get("student_id") or student.get("id") or student.get("register_number"))
    profile = profile_for_student(sid)

    skills = profile.get("skills") or _as_list(student.get("skills"))
    projects = profile.get("projects") or []
    internships = profile.get("internships") or []
    certs = profile.get("certifications") or []
    department = str(profile.get("department") or student.get("department") or student.get("branch") or "")
    cgpa = float(profile.get("cgpa") or student.get("cgpa") or 0)

    role_title = job.get("role_title") or job.get("role") or ""
    job_text = " ".join([
        role_title,
        job.get("job_description") or "",
        job.get("highlight_line") or "",
        job.get("industry") or "",
        " ".join(_as_list(job.get("required_skills"))),
        " ".join(_as_list(job.get("preferred_skills"))),
    ])
    student_text = " ".join([
        " ".join(skills),
        " ".join(project.get("title", "") + " " + project.get("description", "") + " " + project.get("tech_stack", "") for project in projects),
        " ".join(str(item.get("role", "")) + " " + str(item.get("domain", "")) for item in internships),
        " ".join(cert.get("name", "") + " " + cert.get("domain", "") for cert in certs),
    ])

    allowed_departments = {_clean(item).upper() for item in _as_list(job.get("allowed_departments") or job.get("allowed_branches"))}
    dept_score = 1.0 if not allowed_departments or department.upper() in allowed_departments else 0.0
    skill_score = _overlap_score(skills, _as_list(job.get("required_skills")), _as_list(job.get("preferred_skills")))
    role_score = _text_similarity(student_text, job_text)
    location_score = _text_similarity(
        " ".join(str(item.get("mode", "")) for item in internships),
        f"{job.get('location') or ''} {job.get('remote_policy') or ''}",
    )
    company_size_score = _text_similarity(
        " ".join(str(item.get("company_tier", "")) for item in internships),
        f"{job.get('company_size') or ''} {job.get('tier') or ''}",
    )
    category_score = (dept_score * 0.65) + (min(cgpa / 10, 1) * 0.35)
    interest_boost = 0.35 if sid in interested_rank else 0.0

    raw = (
        (skill_score * WEIGHTS["skills"]) +
        (role_score * WEIGHTS["role"]) +
        (location_score * WEIGHTS["location"]) +
        (company_size_score * WEIGHTS["size"]) +
        (category_score * WEIGHTS["category"]) +
        interest_boost
    )
    max_score = sum(WEIGHTS.values()) + 0.35
    score = raw / max_score if max_score else 0.0

    breakdown = {
        "skills": round(skill_score, 3),
        "role": round(role_score, 3),
        "location": round(location_score, 3),
        "size": round(company_size_score, 3),
        "category": round(category_score, 3),
        "interest": round(interest_boost, 3),
        "overall": round(score, 3),
    }
    return score, breakdown


def enrich_student_row(student: Dict[str, Any]) -> Dict[str, Any]:
    sid = str(student.get("student_id") or student.get("id") or student.get("register_number"))
    profile = profile_for_student(sid)
    if not profile:
        return student

    enriched = {**student}
    enriched.setdefault("student_id", sid)
    enriched["full_name"] = enriched.get("full_name") or profile.get("full_name")
    enriched["department"] = enriched.get("department") or profile.get("department")
    enriched["cgpa"] = enriched.get("cgpa") or profile.get("cgpa")
    enriched["skills"] = profile.get("skills") or enriched.get("skills")
    enriched["_talentforge_profile"] = profile
    return enriched
