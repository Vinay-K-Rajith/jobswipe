from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.database import supabase
from app.routers.deps import decode_token
from app.services.cache_control import clear_profile_dependent_caches
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


def _student_update_payload(public_url: str | None, confidence: dict, existing_meta: dict | None = None) -> dict:
    payload = {}
    if public_url:
        payload["resume_url"] = public_url
    if existing_meta:
        payload["resume_parse_confidence"] = {
            **confidence,
            "profile_meta": existing_meta,
        }
    else:
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

    existing_result = _safe_execute(supabase.table("students").select("resume_parse_confidence").eq("student_id", student_id).maybe_single())
    existing_confidence = existing_result.data.get("resume_parse_confidence") if existing_result and existing_result.data else {}
    existing_meta = (existing_confidence or {}).get("profile_meta") or {}
    update_payload = _student_update_payload(public_url, confidence, existing_meta)
    update_result = _safe_execute(
        supabase.table("students").update(update_payload).eq("student_id", student_id)
    )
    if update_result is not None and not update_result.data:
        _safe_execute(supabase.table("students").update(update_payload).eq("id", student_id))
    clear_profile_dependent_caches()

    return {
        "student_id": student_id,
        "parsed": parsed,
        "confidence": confidence,
        "resume_url": public_url or "",
        "message": "Resume uploaded. Profile details can be completed manually.",
    }
