"""
Resume Parser: robust multi-format PDF extractor for the ML pipeline.

Returns (result, confidence) from parse_resume().
"""

from __future__ import annotations

import io
import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

try:
    import pdfplumber

    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


DEFAULT_KNOWN_SKILLS = {
    "python", "java", "c", "c++", "c#", "javascript", "typescript", "go", "rust",
    "r", "matlab", "scala", "kotlin", "swift", "php", "ruby", "bash", "shell",
    "html", "css", "react", "angular", "vue", "next.js", "nextjs", "node.js",
    "nodejs", "express", "express.js", "django", "flask", "fastapi", "spring", "springboot", "sql", "mysql",
    "postgresql", "mongodb", "redis", "sqlite", "pandas", "numpy",
    "scikit-learn", "sklearn", "tensorflow", "pytorch", "keras", "xgboost",
    "lightgbm", "opencv", "nltk", "spacy", "huggingface", "transformers",
    "deep learning", "machine learning", "nlp", "computer vision", "data analysis",
    "data science", "aws", "azure", "gcp", "docker", "kubernetes", "jenkins",
    "git", "github", "gitlab", "linux", "terraform", "ansible", "tableau",
    "powerbi", "excel", "hadoop", "spark", "kafka", "android", "ios", "flutter",
    "rest api", "restapi", "graphql", "microservices", "agile", "scrum",
    "scada", "powerworld", "power world", "pscad", "etap", "simulink", "ltspice",
    "pspice", "proteus", "multisim", "vivado", "vhdl", "verilog", "fpga",
    "cadence", "xilinx", "arduino", "raspberry pi", "embedded c", "iot",
    "signal processing", "power systems", "plc", "hmi", "autocad", "solidworks",
    "catia", "ansys", "creo", "fusion 360", "blender", "maya", "unity",
    "unreal engine", "godot", "opengl", "glsl", "photoshop", "illustrator",
    "figma", "firebase", "websockets", "real-time systems", "kali linux",
    "nmap", "wireshark", "network security", "cybersecurity", "power bi",
    "d3.js", "dash", "plotly", "seaborn", "matplotlib", "prophet",
}


def _skill_key(value: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", value.lower()).strip()


def _load_dynamic_skills() -> set[str]:
    skills = set(DEFAULT_KNOWN_SKILLS)
    candidate_paths = []
    env_path = os.getenv("JOBSWIPE_SKILL_VOCAB_PATH")
    if env_path:
        candidate_paths.append(env_path)

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidate_paths.extend([
        os.path.join(backend_dir, "data", "resume_realworld_normalized", "skills.csv"),
        os.path.join(backend_dir, "data", "resume_realworld_raw", "combined_resumes", "ground_truth"),
    ])

    for candidate in candidate_paths:
        if not os.path.exists(candidate):
            continue
        try:
            if os.path.isdir(candidate):
                for path in os.listdir(candidate):
                    if not path.endswith(".json"):
                        continue
                    payload_path = os.path.join(candidate, path)
                    with open(payload_path, "r", encoding="utf-8") as handle:
                        payload = json.load(handle)
                    for skill in (payload.get("ground_truth", {}) or {}).get("all_skills_flat", []) or []:
                        if isinstance(skill, str) and skill.strip():
                            skills.add(skill.strip())
            elif candidate.endswith(".csv"):
                import csv

                with open(candidate, newline="", encoding="utf-8") as handle:
                    for row in csv.DictReader(handle):
                        skill = row.get("skill_name")
                        if skill and skill.strip():
                            skills.add(skill.strip())
            elif candidate.endswith(".json"):
                payload = json.loads(open(candidate, "r", encoding="utf-8").read())
                for skill in payload if isinstance(payload, list) else payload.get("skills", []):
                    if isinstance(skill, str) and skill.strip():
                        skills.add(skill.strip())
        except Exception:
            continue
    return {_skill_key(skill) for skill in skills if _skill_key(skill)}


KNOWN_SKILLS = _load_dynamic_skills()
KNOWN_DEPARTMENTS = {"CSE", "ECE", "EEE", "MECH", "CIVIL", "IT", "AIDS", "AIML", "MBA", "BCA"}
CERT_TIERS = {"Global Premium", "Global Standard", "National", "Local", "NPTEL", "SWAYAM"}

SECTION_ALIASES = {
    "education": ["EDUCATION", "ACADEMIC", "QUALIFICATION", "ACADEMICS"],
    "skills": ["TECHNICAL SKILLS", "SKILLS", "TECHNICAL COMPETENCIES", "CORE COMPETENCIES", "KEY SKILLS", "TECHNOLOGIES"],
    "certifications": ["CERTIFICATIONS", "CERTIFICATES", "COURSES", "ONLINE COURSES", "ACHIEVEMENTS"],
    "projects": ["PROJECTS", "PROJECT WORK", "ACADEMIC PROJECTS", "PERSONAL PROJECTS", "TECHNICAL PROJECTS"],
    "internships": ["INTERNSHIPS", "EXPERIENCE", "WORK EXPERIENCE", "INTERNSHIP", "INDUSTRY EXPERIENCE"],
    "research": ["RESEARCH PUBLICATIONS", "PUBLICATIONS", "PAPERS", "RESEARCH PAPERS", "RESEARCH"],
}


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().upper().strip()


def _default_result() -> Dict[str, Any]:
    return {
        "name": "",
        "department": "",
        "year_of_study": 0,
        "cgpa": 0.0,
        "10th_marks": 0.0,
        "10th_board": "",
        "12th_marks": 0.0,
        "12th_board": "",
        "active_backlogs": 0,
        "skills": [],
        "certifications": [],
        "projects": [],
        "internships": [],
        "research_papers": [],
    }


def _extract_text_fallback(pdf_bytes: bytes) -> str:
    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "\n".join(page.get_text() or "" for page in doc).strip()
    except Exception:
        pass

    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        return ""


def _extract_text_pdfplumber(pdf_bytes: bytes) -> Tuple[str, List[Any], List[int]]:
    if not HAS_PDFPLUMBER:
        return _extract_text_fallback(pdf_bytes), [], []

    full_text = ""
    all_tables: List[Any] = []
    page_table_counts: List[int] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            full_text += page_text + "\n"
            tables = []
            try:
                tables = page.extract_tables({
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                    "snap_tolerance": 3,
                }) or []
                if not tables:
                    tables = page.extract_tables({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                        "keep_blank_chars": True,
                    }) or []
            except Exception:
                tables = []
            real_tables = [t for t in tables if any(any(cell and str(cell).strip() for cell in row) for row in t)]
            page_table_counts.append(len(real_tables))
            all_tables.extend(real_tables)
    return full_text.strip(), all_tables, page_table_counts


def extract_raw(pdf_path: Any) -> Tuple[str, List[Any], bytes, List[int]]:
    """Read a PDF path or bytes and return text, tables, raw bytes, and per-page table counts."""
    if isinstance(pdf_path, (bytes, bytearray)):
        pdf_bytes = bytes(pdf_path)
    else:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    try:
        text, tables, page_table_counts = _extract_text_pdfplumber(pdf_bytes)
    except Exception:
        text, tables, page_table_counts = _extract_text_fallback(pdf_bytes), [], []

    if len(text.split()) < 10:
        fallback = _extract_text_fallback(pdf_bytes)
        if len(fallback.split()) > len(text.split()):
            text = fallback
    return text, tables, pdf_bytes, page_table_counts


def detect_format(pdf_path: Any, raw: Optional[Tuple[str, List[Any], bytes, List[int]]] = None) -> str:
    """Classify a resume as standard_single_column, two_column, table_heavy, latex_generated, or scanned_ocr."""
    text, tables, _, page_table_counts = raw if raw is not None else extract_raw(pdf_path)
    words = text.split()
    if len(words) < 50:
        return "scanned_ocr"
    if any(count > 3 for count in page_table_counts):
        return "table_heavy"
    non_ascii = sum(1 for char in text if ord(char) > 127)
    if non_ascii / max(len(text), 1) > 0.05:
        return "latex_generated"
    lines = [line for line in text.splitlines() if line.strip()]
    narrow_pages = 0
    if lines:
        avg_words_per_line = len(words) / len(lines)
        if avg_words_per_line < 6 and len(lines) > 20:
            narrow_pages = 1
    if narrow_pages:
        return "two_column"
    if len(tables) >= 3:
        return "table_heavy"
    return "standard_single_column"


def segment_sections(lines: List[str]) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {key: [] for key in SECTION_ALIASES}
    sections["header"] = []
    current = "header"
    alias_lookup = {
        _normalize(alias): section
        for section, aliases in SECTION_ALIASES.items()
        for alias in aliases
    }
    for line in lines:
        norm = _normalize(re.sub(r"[:\-]+$", "", line.strip()))
        if norm in alias_lookup:
            current = alias_lookup[norm]
            continue
        sections[current].append(line)
    return sections


def _extract_header(header_lines: List[str], log: List[str]) -> Dict[str, Any]:
    result = {"name": "", "department": "", "year_of_study": 0, "cgpa": 0.0}
    full_text = " ".join(header_lines)
    for line in header_lines:
        stripped = line.strip()
        if stripped and not re.search(r"CGPA|Year|\|", stripped, re.IGNORECASE):
            result["name"] = stripped
            log.append(f"name: found '{stripped}' [high]")
            break

    dept_match = re.search(r"\b(" + "|".join(sorted(KNOWN_DEPARTMENTS)) + r")\b", full_text)
    if dept_match:
        result["department"] = dept_match.group(1)
        log.append(f"department: found '{result['department']}' [high]")

    year_match = re.search(r"Year\s*(\d)", full_text, re.IGNORECASE)
    if year_match:
        result["year_of_study"] = int(year_match.group(1))
        log.append(f"year_of_study: {result['year_of_study']} [high]")

    cgpa = _find_cgpa(full_text)
    if cgpa:
        result["cgpa"] = cgpa
        log.append(f"cgpa: {cgpa} via header regex [high]")
    return result


def _find_cgpa(text: str) -> float:
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    for pattern in [
        r"(?:C\s*\.?\s*G\s*\.?\s*P\s*\.?\s*A|CGPA|GPA|CPI|Grade Point Average)\s*(?:[:=\-]|is|of|score)?\s*(\d+(?:\.\d+)?)",
        r"(?:C\s*\.?\s*G\s*\.?\s*P\s*\.?\s*A|CGPA|GPA|CPI|Grade Point Average).*?(\d+(?:\.\d+)?)\s*(?:/|out\s+of)\s*10",
        r"(?:Current|Overall|Aggregate|Academic)\s+(?:CGPA|GPA|CPI|score)\s*(?:[:=\-]|is)?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d{1,2})?)\s*/\s*10",
        r"Cumulative.*?(\d+(?:\.\d+)?)",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if 0 < value <= 10:
                return value
    return 0.0


def _looks_like_resume(text: str, result: Dict[str, Any]) -> Tuple[bool, int, str]:
    normalized = _normalize(text)
    words = re.findall(r"[A-Za-z0-9+#.]+", text)
    score = 0
    reasons = []

    contact_hits = 0
    if re.search(r"[\w.+-]+@[\w.-]+\.\w+", text):
        contact_hits += 1
    if re.search(r"(?:\+?\d[\s-]?){8,}", text):
        contact_hits += 1
    if re.search(r"\b(?:LINKEDIN|GITHUB|PORTFOLIO)\b", normalized):
        contact_hits += 1
    if contact_hits:
        score += 1
        reasons.append("contact")

    section_groups = {
        "education": r"\b(EDUCATION|ACADEMIC|QUALIFICATION|CGPA|GPA|CPI|UNIVERSITY|COLLEGE|SCHOOL)\b",
        "skills": r"\b(TECHNICAL SKILLS|SKILLS|TECHNOLOGIES|PROGRAMMING|TOOLS)\b",
        "projects": r"\b(PROJECTS?|PROJECT WORK|PORTFOLIO)\b",
        "experience": r"\b(EXPERIENCE|INTERNSHIPS?|WORK EXPERIENCE|EMPLOYMENT)\b",
        "certifications": r"\b(CERTIFICATIONS?|CERTIFICATES?|COURSES?)\b",
    }
    matched_sections = [name for name, pattern in section_groups.items() if re.search(pattern, normalized)]
    score += min(len(matched_sections), 4)
    reasons.extend(matched_sections)

    if result.get("cgpa", 0.0):
        score += 1
        reasons.append("cgpa")
    if len(result.get("skills", [])) >= 2:
        score += 1
        reasons.append("parsed_skills")
    if result.get("projects") or result.get("internships"):
        score += 1
        reasons.append("parsed_work")

    poster_terms = len(re.findall(r"\b(POSTER|SYMPOSIUM|WORKSHOP|WEBINAR|CONFERENCE|REGISTER|VENUE|CHIEF GUEST|DATE|TIME)\b", normalized))
    if poster_terms >= 4 and score < 5:
        return False, score, "This PDF looks like an event poster or flyer, not a resume."
    if len(words) < 35 and score < 5:
        return False, score, "This PDF does not contain enough resume text to parse."
    if score < 3:
        return False, score, "This PDF does not include enough resume sections such as education, skills, projects, or experience."
    return True, score, ", ".join(reasons[:6])


def _extract_education(edu_lines: List[str], tables: List[Any], log: List[str]) -> Dict[str, Any]:
    result = {
        "cgpa": 0.0,
        "10th_marks": 0.0,
        "10th_board": "",
        "12th_marks": 0.0,
        "12th_board": "",
        "active_backlogs": 0,
    }
    full_text = " ".join(edu_lines)
    cgpa = _find_cgpa(full_text)
    if cgpa:
        result["cgpa"] = cgpa
        log.append(f"cgpa: {cgpa} from education section [high]")

    def read_edu_line(line: str, source: str) -> None:
        line_n = _normalize(line)
        if "CLASS XII" in line_n or "12TH" in line_n or "HSC" in line_n or "HIGHER SECONDARY" in line_n:
            board = re.search(r"\b(CBSE|ICSE|HSC|State)\b", line, re.IGNORECASE)
            marks = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%", line)
            if board and not result["12th_board"]:
                result["12th_board"] = board.group(1).title()
                log.append(f"12th_board: '{result['12th_board']}' {source}")
            if marks and result["12th_marks"] == 0.0:
                result["12th_marks"] = float(marks.group(1))
                log.append(f"12th_marks: {result['12th_marks']} {source}")
        elif "CLASS X" in line_n or "10TH" in line_n or "SSC" in line_n or "SECONDARY" in line_n:
            board = re.search(r"\b(CBSE|ICSE|State|Matriculation)\b", line, re.IGNORECASE)
            marks = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%", line)
            if board and not result["10th_board"]:
                result["10th_board"] = board.group(1).title()
                log.append(f"10th_board: '{result['10th_board']}' {source}")
            if marks and result["10th_marks"] == 0.0:
                result["10th_marks"] = float(marks.group(1))
                log.append(f"10th_marks: {result['10th_marks']} {source}")

    for line in edu_lines:
        read_edu_line(line, "[high]")

    backlog = re.search(r"(\d+)\s*active", full_text, re.IGNORECASE)
    if backlog:
        result["active_backlogs"] = int(backlog.group(1))
        log.append(f"active_backlogs: {result['active_backlogs']} [high]")

    for table in tables:
        for row in table:
            cells = [str(cell or "").strip() for cell in row]
            row_text = " | ".join(cells)
            read_edu_line(row_text, "from table [medium]")
            if result["cgpa"] == 0.0:
                cgpa = _find_cgpa(row_text)
                if cgpa:
                    result["cgpa"] = cgpa
                    log.append(f"cgpa: {cgpa} from table [medium]")
    return result


def _extract_skills(skill_lines: List[str], full_text: str, tables: List[Any], log: List[str]) -> List[Dict[str, str]]:
    skills: List[Dict[str, str]] = []
    seen = set()

    def add(name: str, proficiency: str, source: str) -> None:
        clean = re.sub(r"\s*\(\d+\s+verified\)", "", name).strip(" -;|")
        clean = re.sub(r"^[\u2022*\-•]+\s*", "", clean)
        clean = re.sub(r"^(Languages|Programming|Backend\s*&\s*Systems|ML\s*&\s*Data|Databases\s*&\s*Cloud|Tools|Frameworks|Platforms)\s*:\s*", "", clean, flags=re.IGNORECASE)
        clean = clean.strip(" -;|")
        key = _skill_key(clean)
        if key in {"beginner", "intermediate", "advanced", "expert", "proficient"}:
            return
        if key and key not in seen and len(key) >= 2:
            seen.add(key)
            skills.append({"skill_name": clean, "proficiency": proficiency})
            log.append(f"skill '{clean}': {source}")

    prof_pattern = re.compile(r"(Advanced|Intermediate|Beginner|Expert|Proficient)[:\s]+(.+)", re.IGNORECASE)
    for line in skill_lines:
        match = prof_pattern.match(line.strip())
        if match:
            proficiency = match.group(1).capitalize()
            if proficiency in {"Expert", "Proficient"}:
                proficiency = "Advanced"
            for skill in re.split(r"[,;|/•\u2022]", match.group(2)):
                add(skill, proficiency, "proficiency prefix [high]")

    if not skills:
        for line in skill_lines:
            clean = re.sub(r"^[*\-]+\s*", "", line.strip())
            if clean and len(clean) < 90:
                for skill in re.split(r"[,;|/•\u2022]", clean):
                    add(skill, "Intermediate", "section fallback [medium]")

    text_keyed = _skill_key(full_text)
    for skill in sorted(KNOWN_SKILLS, key=len, reverse=True):
        if re.search(r"(?<![a-z0-9+#])" + re.escape(skill) + r"(?![a-z0-9+#])", text_keyed):
            add(skill.title(), "Intermediate", "vocabulary scan [low]")

    for table in tables:
        for row in table:
            for cell in row:
                cell_text = str(cell or "").strip()
                if 2 <= len(cell_text) <= 50:
                    cell_key = _skill_key(cell_text)
                    if any(re.search(r"(?<![a-z0-9+#])" + re.escape(skill) + r"(?![a-z0-9+#])", cell_key) for skill in KNOWN_SKILLS):
                        add(cell_text, "Intermediate", "table cell [medium]")
    return skills


def _extract_certifications(cert_lines: List[str], tables: List[Any], log: List[str]) -> List[Dict[str, Any]]:
    certs: List[Dict[str, Any]] = []
    seen = set()
    structured = re.compile(r"(.+?)\s*(?:-|--|---|\u2013|\u2014|â€”)\s*(.+?)\s*\((\d{4})\)\s*\[(.+?)\]")
    loose = re.compile(r"(.+?)\s*(?:-|--|---|\u2013|\u2014|â€”)\s*(.+?)\s*\((\d{4})\)")
    tier_pat = re.compile(r"(" + "|".join(re.escape(t) for t in CERT_TIERS) + r")", re.IGNORECASE)

    def add(name: str, issuer: str, year: Any, tier: str, source: str) -> None:
        key = name.lower()[:40]
        if key in seen:
            return
        seen.add(key)
        certs.append({
            "cert_name": name.strip(),
            "issuing_body": issuer.strip(),
            "tier": tier.strip(),
            "year_obtained": int(year) if str(year).isdigit() else 0,
        })
        log.append(f"cert '{name.strip()}': {source}")

    for source_lines, source in [(cert_lines, "[high]"), ([" | ".join(str(c or "") for c in row) for table in tables for row in table], "table [medium]")]:
        for line in source_lines:
            match = structured.search(line)
            if match:
                add(match.group(1), match.group(2), match.group(3), match.group(4), source)
                continue
            match = loose.search(line)
            if match:
                tier = tier_pat.search(line)
                add(match.group(1), match.group(2), match.group(3), tier.group(1) if tier else "National", source)
    return certs


def _extract_projects(lines: List[str], log: List[str]) -> List[Dict[str, str]]:
    projects: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None
    complexity_pat = re.compile(r"\[(Basic|Intermediate|Advanced|Complex)\]", re.IGNORECASE)
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        comp = complexity_pat.search(stripped)
        if comp:
            if current:
                projects.append(current)
            title = complexity_pat.sub("", stripped).strip(" |-")
            current = {"project_title": title, "complexity": comp.group(1).capitalize(), "tech_stack": "", "domain": ""}
            log.append(f"project: '{title}' [high]")
            continue
        if current:
            tech = re.search(r"Tech(?:nology|nologies)?[:\s]+(.+?)(?:\s*\||$)", stripped, re.IGNORECASE)
            domain = re.search(r"Domain[:\s]+(.+?)(?:\s*\||$)", stripped, re.IGNORECASE)
            if tech:
                current["tech_stack"] = tech.group(1).strip()
            if domain:
                current["domain"] = domain.group(1).strip()
    if current:
        projects.append(current)
    if not projects:
        for line in lines:
            stripped = line.strip()
            if 8 < len(stripped) < 100 and not stripped.isupper():
                projects.append({"project_title": stripped, "complexity": "Unknown", "tech_stack": "", "domain": ""})
                log.append(f"project: '{stripped}' fallback [low]")
                if len(projects) >= 5:
                    break
    return projects[:6]


def _extract_internships(lines: List[str], log: List[str]) -> List[Dict[str, Any]]:
    internships: List[Dict[str, Any]] = []
    pattern = re.compile(r"(.+?)\s+at\s+(.+?)(?:\s*\((.+?)\))?\s*(?:-|--|---|\u2013|\u2014|â€”)\s*([\d.]+)\s*months?", re.IGNORECASE)
    for line in lines:
        match = pattern.search(line.strip())
        if match:
            internships.append({
                "role": match.group(1).strip(),
                "company_name": match.group(2).strip(),
                "duration_months": float(match.group(4)),
                "company_tier": (match.group(3) or "Unknown").strip(),
            })
            log.append(f"internship: '{match.group(1).strip()}' [high]")
    return internships


def _extract_research(lines: List[str], log: List[str]) -> List[Dict[str, str]]:
    papers: List[Dict[str, str]] = []
    for line in lines:
        stripped = line.strip()
        match = re.match(r"(.+?)\s*(?:-|--|---|\u2013|\u2014|â€”)\s*(.+?)(?:\s*\((.+?)\))?\s*\[", stripped)
        if match:
            papers.append({"title": match.group(1).strip(), "venue": match.group(2).strip(), "tier": (match.group(3) or "Unknown").strip()})
            log.append(f"paper: '{match.group(1)[:40]}' [high]")
        elif len(stripped) > 15:
            papers.append({"title": stripped[:100], "venue": "Unknown", "tier": "Unknown"})
            log.append(f"paper: '{stripped[:40]}' fallback [low]")
    return papers[:5]


def _extract_all_sections(sections: Dict[str, List[str]], tables: List[Any], full_text: str, log: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    result.update(_extract_header(sections.get("header", []), log))
    education = _extract_education(sections.get("education", []), tables, log)
    if result.get("cgpa", 0.0) == 0.0 and education["cgpa"]:
        result["cgpa"] = education["cgpa"]
    for key in ["10th_marks", "10th_board", "12th_marks", "12th_board", "active_backlogs"]:
        result[key] = education[key]
    if result.get("cgpa", 0.0) == 0.0:
        cgpa = _find_cgpa(full_text)
        if cgpa:
            result["cgpa"] = cgpa
            log.append(f"cgpa: {cgpa} full-text scan [medium]")
    result["skills"] = _extract_skills(sections.get("skills", []), full_text, tables, log)
    result["certifications"] = _extract_certifications(sections.get("certifications", []), tables, log)
    result["projects"] = _extract_projects(sections.get("projects", []), log)
    result["internships"] = _extract_internships(sections.get("internships", []), log)
    result["research_papers"] = _extract_research(sections.get("research", []), log)
    return result


def _parse_table_heavy(text: str, tables: List[Any], log: List[str]) -> Dict[str, Any]:
    log.append("Format: table_heavy - flattening table cells")
    table_text = "\n".join(" | ".join(str(c or "").strip() for c in row) for table in tables for row in table)
    combined = f"{text}\n{table_text}"
    return _extract_all_sections(segment_sections(combined.splitlines()), tables, combined, log)


def _parse_scanned(pdf_bytes: bytes, log: List[str]) -> Dict[str, Any]:
    log.append("Format: scanned_ocr - attempting OCR")
    try:
        import fitz
        import pytesseract
        from PIL import Image

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        ocr_text = ""
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text += pytesseract.image_to_string(img) + "\n"
        if ocr_text.strip():
            log.append("OCR: text extracted successfully")
            return _extract_all_sections(segment_sections(ocr_text.splitlines()), [], ocr_text, log)
        log.append("OCR: returned empty text")
    except ImportError:
        log.append("OCR: pytesseract/PyMuPDF unavailable")
    except Exception as exc:
        log.append(f"OCR: failed with {exc}")
    return {}


def _score_confidence(result: Dict[str, Any], log: List[str]) -> Dict[str, Any]:
    def field_level(field_name: str) -> str:
        entries = [entry for entry in log if entry.startswith(field_name + ":")]
        if not entries:
            return "low"
        latest = entries[-1]
        if "[high]" in latest:
            return "high"
        if "[medium]" in latest:
            return "medium"
        return "low"

    cgpa = field_level("cgpa") if result.get("cgpa", 0.0) else "low"
    skills = "high" if len(result.get("skills", [])) >= 3 else ("medium" if result.get("skills") else "low")
    certs = "high" if result.get("certifications") else "not_found"
    overall = "high" if result.get("cgpa", 0.0) and result.get("skills") else ("medium" if result.get("cgpa", 0.0) or result.get("skills") else "low")
    missing = []
    for key in ["cgpa", "skills"]:
        value = result.get(key)
        if value in (0, 0.0, "", [], None):
            missing.append(key)
    return {"cgpa": cgpa, "skills": skills, "certifications": certs, "overall": overall, "fields_missing": missing}


def parse_resume(pdf_path: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse a resume PDF path or bytes and return (result, confidence)."""
    log: List[str] = []
    empty = _default_result()
    try:
        raw = extract_raw(pdf_path)
        text, tables, pdf_bytes, _ = raw
    except Exception as exc:
        log.append(f"extraction failed: {exc}")
        confidence = _score_confidence(empty, log)
        confidence.update({"format_type": "unknown", "extraction_log": log})
        return empty, confidence

    fmt = detect_format(pdf_path, raw=raw)
    log.append(f"format_detected: {fmt}")
    if fmt == "scanned_ocr":
        extracted = _parse_scanned(pdf_bytes, log) or empty.copy()
    elif fmt == "table_heavy":
        extracted = _parse_table_heavy(text, tables, log)
    else:
        extracted = _extract_all_sections(segment_sections(text.splitlines()), tables, text, log)

    result = {**empty, **extracted}
    confidence = _score_confidence(result, log)
    is_resume, resume_score, resume_reason = _looks_like_resume(text, result)
    confidence.update({
        "format_type": fmt,
        "extraction_log": log,
        "is_resume": is_resume,
        "resume_score": resume_score,
        "resume_reason": resume_reason,
    })
    return result, confidence


def parse_resume_from_bytes(pdf_bytes: bytes) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    return parse_resume(pdf_bytes)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python resume_parser.py <path_to_resume.pdf>")
        raise SystemExit(1)
    parsed, confidence_info = parse_resume(sys.argv[1])
    print(json.dumps(parsed, indent=2))
    print(json.dumps({k: v for k, v in confidence_info.items() if k != "extraction_log"}, indent=2))
