from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.database import supabase
from app.routers.deps import decode_token
from src.preprocessing.resume_parser import parse_resume

router = APIRouter(prefix="/resume", tags=["resume"])


def _check_resume_upload_permission(student_id: str, payload: dict):
    if payload.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student token required")
    subject = str(payload.get("sub") or "")
    if subject and subject == student_id:
        return
    raise HTTPException(status_code=403, detail="You can only upload resumes for permitted student profiles")


def _safe_execute(builder):
    try:
        return builder.execute()
    except Exception as exc:
        print(f"Supabase resume sync warning: {exc}")
        return None


def _replace_child_rows(student_id: str, table: str, rows: list[dict]):
    _safe_execute(supabase.table(table).delete().eq("student_id", student_id))
    if rows:
        _safe_execute(supabase.table(table).insert(rows))


def _student_update_payload(parsed: dict, public_url: str | None, confidence: dict) -> dict:
    payload = {
        "skills": [item["skill_name"] for item in parsed.get("skills", []) if item.get("skill_name")],
        "certifications": [item["cert_name"] for item in parsed.get("certifications", []) if item.get("cert_name")],
        "projects": [item["project_title"] for item in parsed.get("projects", []) if item.get("project_title")],
    }
    for key in [
        "department",
        "year_of_study",
        "cgpa",
        "10th_marks",
        "10th_board",
        "12th_marks",
        "12th_board",
        "active_backlogs",
    ]:
        value = parsed.get(key)
        if value not in ("", None, [], 0, 0.0):
            payload[key] = value
    if parsed.get("name"):
        payload["full_name"] = parsed["name"]
        payload["name"] = parsed["name"]
    if public_url:
        payload["resume_url"] = public_url
    payload["resume_parse_confidence"] = confidence
    return payload


def _sync_parsed_children(student_id: str, parsed: dict):
    _replace_child_rows(student_id, "skills", [
        {
            "student_id": student_id,
            "skill_name": item.get("skill_name", ""),
            "proficiency": item.get("proficiency", "Intermediate"),
            "verified": False,
        }
        for item in parsed.get("skills", [])
        if item.get("skill_name")
    ])

    _replace_child_rows(student_id, "certifications", [
        {
            "cert_id": f"{student_id}_resume_cert_{idx}",
            "student_id": student_id,
            "cert_name": item.get("cert_name", ""),
            "issuing_body": item.get("issuing_body", ""),
            "tier": item.get("tier", ""),
            "year_obtained": item.get("year_obtained") or None,
        }
        for idx, item in enumerate(parsed.get("certifications", []), 1)
        if item.get("cert_name")
    ])

    _replace_child_rows(student_id, "projects", [
        {
            "project_id": f"{student_id}_resume_project_{idx}",
            "student_id": student_id,
            "project_title": item.get("project_title", ""),
            "domain": item.get("domain", ""),
            "tech_stack": item.get("tech_stack", ""),
            "complexity": item.get("complexity", "Unknown"),
        }
        for idx, item in enumerate(parsed.get("projects", []), 1)
        if item.get("project_title")
    ])

    _replace_child_rows(student_id, "internships", [
        {
            "internship_id": f"{student_id}_resume_internship_{idx}",
            "student_id": student_id,
            "role": item.get("role", ""),
            "company_name": item.get("company_name", ""),
            "duration_months": item.get("duration_months") or 0,
            "company_tier": item.get("company_tier", "Unknown"),
        }
        for idx, item in enumerate(parsed.get("internships", []), 1)
        if item.get("role") or item.get("company_name")
    ])

    _replace_child_rows(student_id, "research_papers", [
        {
            "paper_id": f"{student_id}_resume_paper_{idx}",
            "student_id": student_id,
            "title": item.get("title", ""),
            "publication_venue": item.get("venue", ""),
            "tier": item.get("tier", "Unknown"),
        }
        for idx, item in enumerate(parsed.get("research_papers", []), 1)
        if item.get("title")
    ])


@router.post("/upload/{student_id}")
async def upload_resume(student_id: str, file: UploadFile = File(...), payload=Depends(decode_token)):
    _check_resume_upload_permission(student_id, payload)
    if file.content_type not in {"application/pdf", "application/octet-stream"} and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are allowed")

    contents = await file.read()
    parsed, confidence = parse_resume(contents)
    if not confidence.get("is_resume"):
        raise HTTPException(
            status_code=400,
            detail=confidence.get("resume_reason") or "This PDF does not look like a resume.",
        )

    path = f"resumes/{student_id}.pdf"
    public_url = None
    try:
        storage = supabase.storage.from_("resumes")
        storage.remove([path])
        storage.upload(path, contents, {"content-type": "application/pdf", "upsert": "true"})
        public_url_resp = storage.get_public_url(path)
        if isinstance(public_url_resp, dict):
            public_url = public_url_resp.get("publicURL") or public_url_resp.get("public_url") or public_url_resp.get("url")
        elif isinstance(public_url_resp, str):
            public_url = public_url_resp
    except Exception:
        print("Resume storage upload skipped or failed; continuing with database parse")

    update_payload = _student_update_payload(parsed, public_url, confidence)
    update_result = _safe_execute(
        supabase.table("students").update(update_payload).eq("student_id", student_id)
    )
    if update_result is not None and not update_result.data:
        _safe_execute(supabase.table("students").update(update_payload).eq("id", student_id))
    _sync_parsed_children(student_id, parsed)

    return {
        "student_id": student_id,
        "parsed": parsed,
        "confidence": confidence,
        "resume_url": public_url or "",
        "message": "Resume parsed and student profile synced",
    }
