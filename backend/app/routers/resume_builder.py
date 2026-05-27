import os
from io import BytesIO
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from groq import Groq
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

try:
    from reportlab.lib.units import pt
except ImportError:
    pt = 1

from app.database import supabase
from app.routers.deps import get_current_user
from app.routers.swipe import execute_supabase

router = APIRouter(prefix="/resume-builder", tags=["resume-builder"])


class ResumePreviewRequest(BaseModel):
    student_id: str
    template_id: str
    resume_text: Optional[str] = None
    instruction: Optional[str] = None


class ResumeDownloadRequest(BaseModel):
    student_id: str
    resume_text: str


def current_student_id(user: Dict[str, Any]) -> str:
    return str(user.get("student_id") or user.get("id") or user.get("register_number"))


def ensure_owns_student(student_id: str, user: Dict[str, Any]) -> None:
    if str(student_id) != current_student_id(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own resume builder.")


def groq_resume_text(system_prompt: str, user_prompt: str) -> str:
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Resume generation failed: {exc}",
        )


def fetch_student_resume_data(student_id: str) -> Dict[str, Any]:
    student_result = execute_supabase(
        lambda: supabase.table("students")
        .select("full_name, department, cgpa, batch_year, email")
        .eq("student_id", student_id)
        .maybe_single()
    )
    student = student_result.data if student_result else None
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    skills_result = execute_supabase(
        lambda: supabase.table("skills")
        .select("skill_name")
        .eq("student_id", student_id)
    )
    projects_result = execute_supabase(
        lambda: supabase.table("projects")
        .select("project_title, domain, tech_stack")
        .eq("student_id", student_id)
        .limit(4)
    )
    certs_result = execute_supabase(
        lambda: supabase.table("certifications")
        .select("cert_name, issuing_body")
        .eq("student_id", student_id)
        .limit(4)
    )
    internships_result = execute_supabase(
        lambda: supabase.table("internships")
        .select("company_name, role, duration_months")
        .eq("student_id", student_id)
        .limit(3)
    )

    return {
        "student": student,
        "skills": skills_result.data or [],
        "projects": projects_result.data or [],
        "certifications": certs_result.data or [],
        "internships": internships_result.data or [],
    }


def build_generation_prompt(data: Dict[str, Any]) -> str:
    student = data["student"]
    skills = ", ".join(str(item.get("skill_name") or "").strip() for item in data["skills"] if item.get("skill_name"))
    projects = "\n".join(
        f"{item.get('project_title') or ''} | {item.get('domain') or ''} | {item.get('tech_stack') or ''}"
        for item in data["projects"]
    )
    certifications = "\n".join(
        f"{item.get('cert_name') or ''} | {item.get('issuing_body') or ''}"
        for item in data["certifications"]
    )
    internships = "\n".join(
        f"{item.get('company_name') or ''} | {item.get('role') or ''} | {item.get('duration_months') or ''} months"
        for item in data["internships"]
    )

    return (
        "Generate a resume for this candidate:\n"
        f"NAME: {student.get('full_name') or ''}\n"
        f"EMAIL: {student.get('email') or ''}\n"
        f"DEPARTMENT: {student.get('department') or ''}\n"
        f"CGPA: {student.get('cgpa') or ''}\n"
        f"BATCH YEAR: {student.get('batch_year') or ''}\n"
        f"SKILLS: {skills}\n"
        f"PROJECTS: {projects}\n"
        f"CERTIFICATIONS: {certifications}\n"
        f"INTERNSHIPS: {internships}"
    )


def is_dashed_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and set(stripped) == {"-"}


def is_section_header(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and stripped == stripped.upper() and any(char.isalpha() for char in stripped)


def build_pdf(resume_text: str) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40 * pt,
        rightMargin=40 * pt,
        topMargin=40 * pt,
        bottomMargin=40 * pt,
    )

    getSampleStyleSheet()
    section_style = ParagraphStyle(
        "ResumeSection",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        spaceBefore=12,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "ResumeBody",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
    )
    bullet_style = ParagraphStyle(
        "ResumeBullet",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        leftIndent=12,
    )

    story: List[Any] = []
    lines = resume_text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 6))
            index += 1
            continue

        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if is_section_header(stripped) and is_dashed_line(next_line):
            story.append(Paragraph(escape(stripped), section_style))
            story.append(HRFlowable(width="100%", thickness=0.5))
            index += 2
            continue

        if stripped.startswith("- "):
            story.append(Paragraph(f"•  {escape(stripped[2:])}", bullet_style))
        else:
            story.append(Paragraph(escape(stripped), body_style))
        index += 1

    doc.build(story)
    buffer.seek(0)
    return buffer


@router.post("/preview")
def preview_resume(req: ResumePreviewRequest, user=Depends(get_current_user)):
    ensure_owns_student(req.student_id, user)

    if req.resume_text:
        system_prompt = (
            "You are editing an existing resume. Apply ONLY the requested change. "
            "Do not add any new skills, experience, or qualifications that were not "
            "in the original. Do not modify any section not mentioned in the "
            "instruction. Return only the complete updated resume text with no "
            "explanation or preamble."
        )
        user_prompt = f"Current resume:\n{req.resume_text}\n\nInstruction: {req.instruction or ''}"
    else:
        data = fetch_student_resume_data(req.student_id)
        system_prompt = (
            "You are a resume writer. Generate a professional resume using ONLY "
            "the information provided. Never invent, infer, or add any skills, "
            "experience, projects, or qualifications not explicitly given to you. "
            "Structure the resume with these sections in this exact order: "
            "CONTACT, SUMMARY, EDUCATION, SKILLS, PROJECTS, CERTIFICATIONS, "
            "EXPERIENCE. Write each section header in ALL CAPS followed by a "
            "line of ten dashes. Use a dash character for bullet points. "
            "Keep SUMMARY to 3 sentences maximum. Return only the resume text, "
            "no explanation or preamble."
        )
        user_prompt = build_generation_prompt(data)

    return {"resume_text": groq_resume_text(system_prompt, user_prompt)}


@router.post("/download")
def download_resume(req: ResumeDownloadRequest, user=Depends(get_current_user)):
    ensure_owns_student(req.student_id, user)
    buffer = build_pdf(req.resume_text)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=resume_{req.student_id}.pdf"},
    )
