import os
import re
import json
import asyncio
import subprocess
import tempfile
from io import BytesIO
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from groq import Groq
from pydantic import BaseModel

from app.database import supabase
from app.routers.deps import get_current_user
from app.routers.swipe import execute_supabase

router = APIRouter(prefix="/resume-builder", tags=["resume-builder"])

# ─── ATS action verbs for scoring ───────────────────────────────────────────

_ACTION_VERBS = {
    "achieved", "administered", "analysed", "analyzed", "architected", "automated",
    "built", "collaborated", "configured", "created", "debugged", "delivered",
    "deployed", "designed", "developed", "drove", "engineered", "enhanced",
    "established", "evaluated", "executed", "founded", "generated", "implemented",
    "improved", "increased", "integrated", "launched", "led", "managed",
    "mentored", "migrated", "modernised", "modernized", "optimised", "optimized",
    "orchestrated", "owned", "published", "reduced", "refactored", "researched",
    "resolved", "scaled", "shipped", "spearheaded", "streamlined", "trained",
    "transformed", "validated",
}

# ─── Resume templates ────────────────────────────────────────────────────────

_TEMPLATES = [
    {
        "id": "classic",
        "name": "Classic",
        "description": "Timeless chronological layout — best for campus placements",
        "icon": "📄",
        "section_order": "SUMMARY, EDUCATION, TECHNICAL SKILLS, EXPERIENCE, PROJECTS, CERTIFICATIONS, RESEARCH",
    },
    {
        "id": "technical",
        "name": "Technical",
        "description": "Skills-first layout — ideal for engineering and SDE roles",
        "icon": "⚙️",
        "section_order": "SUMMARY, TECHNICAL SKILLS, PROJECTS, EXPERIENCE, EDUCATION, CERTIFICATIONS",
    },
    {
        "id": "research",
        "name": "Research",
        "description": "Publications and academics up front — best for M.Tech / PhD applications",
        "icon": "🔬",
        "section_order": "SUMMARY, EDUCATION, RESEARCH, TECHNICAL SKILLS, PROJECTS, EXPERIENCE, CERTIFICATIONS",
    },
    {
        "id": "minimal",
        "name": "Minimal",
        "description": "Ultra-clean single-column layout — high ATS parse rate",
        "icon": "✦",
        "section_order": "SUMMARY, EDUCATION, TECHNICAL SKILLS, EXPERIENCE, PROJECTS, CERTIFICATIONS",
    },
]

# ─── LLM format spec ─────────────────────────────────────────────────────────

def _template_prompt(template_id: str) -> str:
    tmpl = next((t for t in _TEMPLATES if t["id"] == template_id), _TEMPLATES[0])
    
    margins = "left=0.75in,top=0.6in,right=0.75in,bottom=0.6in"
    primary_color = "111827"
    secondary_color = "4F46E5"
    
    if template_id == "technical":
        margins = "left=0.6in,top=0.55in,right=0.6in,bottom=0.55in"
        secondary_color = "0D9488"
    elif template_id == "research":
        margins = "left=0.8in,top=0.7in,right=0.8in,bottom=0.7in"
        secondary_color = "1E3A8A"
    elif template_id == "minimal":
        margins = "left=0.75in,top=0.65in,right=0.75in,bottom=0.65in"
        secondary_color = "374151"
        
    return f"""
Generate a professional, high-quality, single-page LaTeX resume. 
The template type requested is: '{tmpl['name']}' ({tmpl['description']}).
Layout section order must be: {tmpl['section_order']}

LATEX COMPILATION CONSTRAINTS:
- Use EXACTLY this document class and package list:
  \\documentclass[10pt,a4paper]{{article}}
  \\usepackage[utf8]{{inputenc}}
  \\usepackage[{margins}]{{geometry}}
  \\usepackage{{xcolor}}
  \\usepackage{{titlesec}}
  \\usepackage{{enumitem}}
  \\usepackage{{hyperref}}
- Define colors exactly like this:
  \\definecolor{{primary}}{{HTML}}{{{primary_color}}}
  \\definecolor{{secondary}}{{HTML}}{{{secondary_color}}}
- Configure hyperref:
  \\hypersetup{{colorlinks=true, urlcolor=secondary, linkcolor=primary, pdfborder={{0 0 0}}}}
- Format sections:
  \\titleformat{{\\section}}{{\\large\\bfseries\\color{{primary}}}}{{}}{{0em}}{{}}[\\titlerule]
  \\titlespacing*{{\\section}}{{0pt}}{{8pt}}{{4pt}}
- Use \\pagestyle{{empty}} to prevent page numbering.
- Start the document body with \\begin{{document}} right after the preamble configuration.
- Center name and contact info at the top (inside the document body):
  \\begin{{center}}
      {{\\LARGE \\bfseries [Name]}} \\\\
      \\vspace{{2pt}}
      \\href{{mailto:[Email]}}{{[Email]}} $|$ [Phone] $|$ \\href{{[LinkedIn]}}{{linkedin.com/in/[username]}} $|$ \\href{{[GitHub]}}{{github.com/[username]}}
  \\end{{center}}
- For itemized lists (bullet points), use:
  \\begin{{itemize}}[leftmargin=*,noitemsep,topsep=2pt]
      \\item ...
  \\end{{itemize}}
- Use \\hfill for right-aligned dates or locations:
  \\textbf{{[Item Title]}} $|$ \\emph{{[Subtitle/Tech]}} \\hfill [Date/Location]
- Omit a section if there is no candidate data for it.
- NEVER include LaTeX packages outside the specified list.
- Keep the content dense enough to fit on EXACTLY ONE PAGE.
- Avoid inventing or inferring ANY data. If a phone, github, or linkedin link is not in the data, omit that item from the contact header or use a clean placeholder only if it's necessary for structure, but prefer omitting it.
- Return ONLY valid, compile-able LaTeX code.
- Do NOT wrap code in markdown code blocks like ```latex or ```. Do NOT include any preamble commentary, no introductions, no side-notes. Start directly with \\documentclass and end with \\end{{document}}.
""".strip()


# ─── Pydantic models ─────────────────────────────────────────────────────────

class ResumePreviewRequest(BaseModel):
    student_id: str
    template_id: str = "classic"
    resume_text: Optional[str] = None
    instruction: Optional[str] = None
    target_job_id: Optional[str] = None


class ResumeDownloadRequest(BaseModel):
    student_id: str
    resume_text: str


class ResumeScoreRequest(BaseModel):
    student_id: str
    resume_text: str
    target_job_id: Optional[str] = None


class ResumeStreamRequest(BaseModel):
    student_id: str
    template_id: str = "classic"
    target_job_id: Optional[str] = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _current_student_id(user: Dict[str, Any]) -> str:
    return str(user.get("student_id") or user.get("id") or user.get("register_number"))


def _ensure_owns(student_id: str, user: Dict[str, Any]) -> None:
    if str(student_id) != _current_student_id(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own resume.")


def _groq_client() -> Groq:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GROQ_API_KEY not configured.")
    return Groq(api_key=key)


def _groq(system: str, user_msg: str) -> str:
    try:
        resp = _groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            max_tokens=3000,
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Resume generation failed: {exc}")


def _fetch_data(student_id: str) -> Dict[str, Any]:
    res = execute_supabase(
        lambda: supabase.table("students")
        .select("full_name, department, cgpa, batch_year, email, year_of_study, register_number")
        .eq("student_id", student_id)
        .maybe_single()
    )
    student = res.data if res else None
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    skills = execute_supabase(lambda: supabase.table("skills").select("skill_name, proficiency, verified").eq("student_id", student_id)).data or []
    projects = execute_supabase(lambda: supabase.table("projects").select("project_title, domain, tech_stack, complexity, has_deployment, has_github, duration_weeks").eq("student_id", student_id).limit(6)).data or []
    certs = execute_supabase(lambda: supabase.table("certifications").select("cert_name, issuing_body, tier, domain, year_obtained").eq("student_id", student_id).limit(6)).data or []
    internships = execute_supabase(lambda: supabase.table("internships").select("company_name, role, duration_months, domain, stipend, mode").eq("student_id", student_id).limit(4)).data or []
    papers = execute_supabase(lambda: supabase.table("research_papers").select("title, publication_venue, tier, domain, year_published, is_first_author").eq("student_id", student_id).limit(4)).data or []

    return {
        "student": student,
        "skills": skills,
        "projects": projects,
        "certifications": certs,
        "internships": internships,
        "papers": papers,
    }


def _fetch_job(job_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = execute_supabase(
            lambda: supabase.table("jobs")
            .select("role_title, company_name, required_skills, preferred_skills, job_description")
            .eq("id", job_id)
            .maybe_single()
        )
        return res.data if res else None
    except Exception:
        return None


def _fmt_skill(x: Dict) -> str:
    name = x.get("skill_name", "")
    prof = x.get("proficiency")
    verified = x.get("verified")
    tag = ""
    if verified:
        tag = " ✓"
    elif prof:
        tag = f"({prof})"
    return f"{name}{tag}"


def _build_user_prompt(data: Dict[str, Any], job: Optional[Dict[str, Any]] = None) -> str:
    s = data["student"]
    lines: List[str] = [
        f"NAME: {s.get('full_name') or ''}",
        f"EMAIL: {s.get('email') or ''}",
        f"DEPARTMENT: {s.get('department') or ''}",
        f"CGPA: {s.get('cgpa') or ''}",
        f"BATCH YEAR: {s.get('batch_year') or ''}",
        f"YEAR OF STUDY: {s.get('year_of_study') or ''}",
        f"REGISTER NUMBER: {s.get('register_number') or ''}",
    ]

    skills = [x for x in data["skills"] if x.get("skill_name")]
    if skills:
        lines.append("SKILLS: " + ", ".join(_fmt_skill(x) for x in skills))

    if data["internships"]:
        lines.append("\nINTERNSHIPS:")
        for x in data["internships"]:
            mode = x.get("mode") or ""
            stipend = "with stipend" if x.get("stipend") else ""
            meta = " | ".join(filter(None, [mode, stipend]))
            lines.append(f"  - {x.get('company_name')} | {x.get('role')} | {x.get('duration_months')} months | {x.get('domain')}{(' | ' + meta) if meta else ''}")

    if data["projects"]:
        lines.append("\nPROJECTS:")
        for x in data["projects"]:
            extras = []
            if x.get("has_deployment"):
                extras.append("deployed")
            if x.get("has_github"):
                extras.append("GitHub")
            if x.get("duration_weeks"):
                extras.append(f"{x['duration_weeks']}w")
            extra_str = (" | " + ", ".join(extras)) if extras else ""
            lines.append(f"  - {x.get('project_title')} | {x.get('tech_stack')} | {x.get('domain')} | Complexity: {x.get('complexity')}{extra_str}")

    if data["certifications"]:
        lines.append("\nCERTIFICATIONS:")
        for x in data["certifications"]:
            year = f" ({x.get('year_obtained')})" if x.get("year_obtained") else ""
            lines.append(f"  - {x.get('cert_name')} by {x.get('issuing_body')} (tier: {x.get('tier')}){year}")

    if data["papers"]:
        lines.append("\nRESEARCH PAPERS:")
        for x in data["papers"]:
            first = " [First Author]" if x.get("is_first_author") else ""
            lines.append(f"  - {x.get('title')} | {x.get('publication_venue')} ({x.get('tier')}) {x.get('year_published') or ''}{first}")

    if job:
        req = job.get("required_skills") or []
        pref = job.get("preferred_skills") or []
        if isinstance(req, list):
            req = ", ".join(req)
        if isinstance(pref, list):
            pref = ", ".join(pref)
        lines.append(f"\nTARGET JOB: {job.get('role_title')} at {job.get('company_name')}")
        if req:
            lines.append(f"REQUIRED SKILLS FOR THIS JOB: {req}")
        if pref:
            lines.append(f"PREFERRED SKILLS FOR THIS JOB: {pref}")
        lines.append("NOTE: Emphasise skills and experience most relevant to this target role.")

    return "\n".join(lines)


# ─── ATS Scoring ─────────────────────────────────────────────────────────────

def clean_latex_code(code: str) -> str:
    code = code.strip()
    code = re.sub(r'^```(?:latex)?\s*', '', code, flags=re.IGNORECASE)
    code = re.sub(r'\s*```$', '', code)
    return code.strip()


def latex_to_text(latex_code: str) -> str:
    text = re.sub(r'(?<!\\)%.*', '', latex_code)
    
    body_match = re.search(r'\\begin\{document\}(.*?)\\end\{document\}', text, re.DOTALL)
    if body_match:
        text = body_match.group(1)
        
    text = re.sub(r'\\begin\{[a-zA-Z]+\}(\[[^\]]*\])?', '', text)
    text = re.sub(r'\\end\{[a-zA-Z]+\}', '', text)
    
    text = text.replace(r'\\', '\n')
    text = text.replace(r'\hfill', ' ')
    text = text.replace(r'\bullet', ' • ')
    text = text.replace(r'\item', '\n- ')
    
    text = re.sub(r'\\href\{[^\}]*\}\{([^\}]*)\}', r'\1', text)
    for _ in range(5):
        text = re.sub(r'\\[a-zA-Z]+\*?\{([^\}]*)\}', r'\1', text)
    
    text = re.sub(r'\\[a-zA-Z]+\*?(\[[^\]]*\])?', '', text)
    text = text.replace('{', '').replace('}', '')
    
    text = re.sub(r'(?m)^\s*\d+(?:\.\d+)?(?:pt|in|cm|em|ex|mm|pc|sp|dd|cc|bp)\s*$', '', text)
    text = re.sub(r'(?m)^\s*(empty|plain|headings|myheadings)\s*$', '', text)
    
    lines = []
    for line in text.splitlines():
        cleaned = re.sub(r'\s+', ' ', line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _score_resume(resume_text: str, job: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    section_headers = [h.strip().upper() for h in re.findall(r'\\section\*?\{([^\}]+)\}', resume_text)]
    bullet_lines = [b.strip() for b in re.findall(r'\\item\s+(.*)', resume_text)]
    
    required_sections = {"EDUCATION", "TECHNICAL SKILLS", "SUMMARY"}
    bonus_sections = {"EXPERIENCE", "PROJECTS", "CERTIFICATIONS", "RESEARCH"}
    found_sections = {h for h in section_headers}
    required_found = required_sections & found_sections
    bonus_found = bonus_sections & found_sections
    section_score = round((len(required_found) / len(required_sections)) * 70 + (len(bonus_found) / len(bonus_sections)) * 30)
    missing_required = required_sections - found_sections

    action_hits = sum(
        1 for l in bullet_lines
        if any(l.strip().lower().startswith(v) for v in _ACTION_VERBS)
    )
    verb_score = round((action_hits / len(bullet_lines)) * 100) if bullet_lines else 0

    quant_hits = sum(1 for l in bullet_lines if re.search(r"\d", l))
    quant_score = round((quant_hits / len(bullet_lines)) * 100) if bullet_lines else 0

    plain_text = latex_to_text(resume_text)
    word_count = len(plain_text.split())
    if 300 <= word_count <= 600:
        length_score = 100
    elif word_count < 300:
        length_score = max(0, round((word_count / 300) * 100))
    else:
        length_score = max(0, round(100 - ((word_count - 600) / 4)))

    keyword_score = 50
    matched_keywords: List[str] = []
    missing_keywords: List[str] = []
    if job:
        req = job.get("required_skills") or []
        pref = job.get("preferred_skills") or []
        if isinstance(req, str):
            req = [s.strip() for s in req.split(",") if s.strip()]
        if isinstance(pref, str):
            pref = [s.strip() for s in pref.split(",") if s.strip()]
        all_keywords = req + pref
        if all_keywords:
            text_lower = plain_text.lower()
            matched_keywords = [k for k in all_keywords if k.lower() in text_lower]
            missing_keywords = [k for k in all_keywords if k.lower() not in text_lower]
            keyword_score = round((len(matched_keywords) / len(all_keywords)) * 100)

    overall = round(
        section_score * 0.25 +
        verb_score * 0.25 +
        quant_score * 0.20 +
        length_score * 0.15 +
        keyword_score * 0.15
    )

    def _tip(name: str, score: int) -> str:
        if name == "sections":
            if missing_required:
                return f"Add missing section(s): {', '.join(missing_required)}"
            return "All key sections present — great structure."
        if name == "verbs":
            if score < 60:
                return "Start more bullets with action verbs: Built, Developed, Designed, Implemented…"
            return "Good use of action verbs throughout."
        if name == "quantification":
            if score < 40:
                return "Add numbers to your bullets (e.g. 'Reduced load time by 30%', 'Led a team of 4')."
            return "Good use of metrics to quantify impact."
        if name == "length":
            if word_count < 300:
                return f"Resume is short ({word_count} words). Expand sections to add details."
            if word_count > 600:
                return f"Resume is long ({word_count} words). Trim to one page for best ATS results."
            return f"Ideal length ({word_count} words)."
        if name == "keywords":
            if missing_keywords:
                return f"Missing keywords: {', '.join(missing_keywords[:5])}. Add them where applicable."
            return "Great keyword alignment with the target job."
        return ""

    return {
        "overall": overall,
        "word_count": word_count,
        "dimensions": {
            "sections": {
                "label": "Section Completeness",
                "score": section_score,
                "tip": _tip("sections", section_score),
                "found": sorted(found_sections),
                "missing": sorted(missing_required),
            },
            "action_verbs": {
                "label": "Action Verb Strength",
                "score": verb_score,
                "tip": _tip("verbs", verb_score),
                "bullet_count": len(bullet_lines),
                "strong_bullets": action_hits,
            },
            "quantification": {
                "label": "Quantified Impact",
                "score": quant_score,
                "tip": _tip("quantification", quant_score),
                "quantified_bullets": quant_hits,
            },
            "length": {
                "label": "Length & Density",
                "score": length_score,
                "tip": _tip("length", length_score),
                "word_count": word_count,
            },
            "keywords": {
                "label": "Job Keyword Match",
                "score": keyword_score,
                "tip": _tip("keywords", keyword_score),
                "matched": matched_keywords,
                "missing": missing_keywords,
            },
        },
    }


def build_pdf(resume_text: str) -> BytesIO:
    resume_text = clean_latex_code(resume_text)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(resume_text)
        
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, "resume.tex"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=tmpdir,
                timeout=15
            )
            
        pdf_path = os.path.join(tmpdir, "resume.pdf")
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                return BytesIO(f.read())
        else:
            log_path = os.path.join(tmpdir, "resume.log")
            error_details = ""
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    error_details = f.read()
            else:
                error_details = f"Exit code: {result.returncode}\nStdout: {result.stdout}\nStderr: {result.stderr}"
            
            print(f"LaTeX Compilation Error: {error_details}")
            
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "LaTeX compilation failed. Review the compilation log below.",
                    "log": error_details
                }
            )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/templates")
def list_templates():
    """Return available resume templates."""
    return {"templates": _TEMPLATES}


@router.post("/preview")
def preview_resume(req: ResumePreviewRequest, user=Depends(get_current_user)):
    """Generate or edit resume text via LLM."""
    _ensure_owns(req.student_id, user)

    job: Optional[Dict[str, Any]] = None
    if req.target_job_id:
        job = _fetch_job(req.target_job_id)

    if req.resume_text:
        # Edit mode
        job_context = ""
        if job:
            req_skills = job.get("required_skills") or []
            if isinstance(req_skills, list):
                req_skills = ", ".join(req_skills)
            job_context = (
                f"\n\nThe resume is targeted at: {job.get('role_title')} at {job.get('company_name')}. "
                f"Required skills: {req_skills}. "
                f"Ensure these are prominent where the candidate legitimately has them."
            )
        system = (
            "You are editing an existing ATS resume. Apply ONLY the requested change. "
            "Do not add any skills, experience, or qualifications not in the original. "
            "Do not modify sections not mentioned in the instruction. "
            "Preserve the exact formatting conventions of the original (ALL CAPS headers, --- separators, bullet dashes). "
            "Return only the complete updated resume text with no explanation or preamble."
            + job_context
        )
        user_msg = f"CURRENT RESUME:\n{req.resume_text}\n\nINSTRUCTION: {req.instruction or ''}"
    else:
        # Generate mode
        data = _fetch_data(req.student_id)
        system = (
            "You are a professional resume writer specialising in ATS-optimised resumes for engineering students. "
            "Generate a clean, honest, ATS-friendly resume using ONLY the candidate data provided. "
            "Never invent, infer, or add anything not explicitly given. "
            "Never use tables, columns, graphics, or headers/footers.\n\n"
            + _template_prompt(req.template_id or "classic")
        )
        user_msg = _build_user_prompt(data, job)

    resume_text = _groq(system, user_msg)
    score = _score_resume(resume_text, job)
    return {"resume_text": resume_text, "score": score}


@router.post("/score")
def score_resume(req: ResumeScoreRequest, user=Depends(get_current_user)):
    """Score an existing resume text without regenerating."""
    _ensure_owns(req.student_id, user)
    job = _fetch_job(req.target_job_id) if req.target_job_id else None
    score = _score_resume(req.resume_text, job)
    return score


@router.post("/stream")
async def stream_resume(req: ResumeStreamRequest, user=Depends(get_current_user)):
    """Stream resume generation token-by-token as SSE."""
    _ensure_owns(req.student_id, user)

    data = _fetch_data(req.student_id)
    job = _fetch_job(req.target_job_id) if req.target_job_id else None
    system = (
        "You are a professional resume writer specialising in ATS-optimised resumes for engineering students. "
        "Generate a clean, honest, ATS-friendly resume using ONLY the candidate data provided. "
        "Never invent, infer, or add anything not explicitly given. "
        "Never use tables, columns, graphics, or headers/footers.\n\n"
        + _template_prompt(req.template_id or "classic")
    )
    user_msg = _build_user_prompt(data, job)

    async def event_generator():
        try:
            client = _groq_client()
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                max_tokens=3000,
                temperature=0.3,
                stream=True,
            )
            full_text = ""
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_text += delta
                    payload = json.dumps({"token": delta})
                    yield f"data: {payload}\n\n"
            # Send final score
            job_data = _fetch_job(req.target_job_id) if req.target_job_id else None
            score = _score_resume(full_text, job_data)
            yield f"data: {json.dumps({'done': True, 'full_text': full_text, 'score': score})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/download")
def download_resume(req: ResumeDownloadRequest, user=Depends(get_current_user)):
    """Generate and download resume as a PDF."""
    _ensure_owns(req.student_id, user)
    buf = build_pdf(req.resume_text)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=resume_{req.student_id}.pdf"},
    )
