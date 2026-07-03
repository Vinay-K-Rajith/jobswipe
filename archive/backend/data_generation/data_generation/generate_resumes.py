"""
Resume PDF Generator: Create professional PDF resumes from CSV data.
Uses reportlab for PDF generation.
One resume per student, pulling data from all sub-tables.
"""

import os
import csv
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
RESUME_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'resumes')

# Colors
PRIMARY = HexColor("#1a237e")
SECONDARY = HexColor("#303f9f")
ACCENT = HexColor("#448aff")
TEXT_DARK = HexColor("#212121")
TEXT_MED = HexColor("#424242")
TEXT_LIGHT = HexColor("#757575")
DIVIDER = HexColor("#bdbdbd")


def get_styles():
    """Create custom paragraph styles for resume."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'ResumeName', parent=styles['Title'],
        fontSize=18, textColor=PRIMARY, spaceAfter=2*mm,
        alignment=TA_LEFT, fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        'ResumeSubtitle', parent=styles['Normal'],
        fontSize=10, textColor=TEXT_MED, spaceAfter=3*mm,
        fontName='Helvetica'
    ))
    styles.add(ParagraphStyle(
        'SectionHeader', parent=styles['Heading2'],
        fontSize=12, textColor=PRIMARY, spaceBefore=4*mm,
        spaceAfter=2*mm, fontName='Helvetica-Bold',
        borderWidth=0, borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        'ItemTitle', parent=styles['Normal'],
        fontSize=10, textColor=TEXT_DARK, spaceBefore=1*mm,
        fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        'ItemDetail', parent=styles['Normal'],
        fontSize=9, textColor=TEXT_MED, leftIndent=10,
        fontName='Helvetica'
    ))
    styles.add(ParagraphStyle(
        'ItemBullet', parent=styles['Normal'],
        fontSize=9, textColor=TEXT_MED, leftIndent=15,
        fontName='Helvetica', bulletIndent=10,
    ))

    return styles


def build_resume_elements(student, certs, projects, internships, papers, skills, styles):
    """Build the flowable elements for one student's resume."""
    elements = []

    # --- HEADER ---
    elements.append(Paragraph(student["full_name"], styles["ResumeName"]))
    subtitle = f"{student['department']} | Year {student['year_of_study']} | CGPA: {student['cgpa']}"
    elements.append(Paragraph(subtitle, styles["ResumeSubtitle"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=DIVIDER, spaceBefore=1*mm, spaceAfter=3*mm))

    # --- EDUCATION ---
    elements.append(Paragraph("EDUCATION", styles["SectionHeader"]))

    edu_data = [
        ["Degree/Level", "Board/University", "Score"],
        [f"B.Tech / B.E. ({student['department']})", "University", f"CGPA: {student['cgpa']}"],
        ["Class XII", student["12th_board"], f"{student['12th_marks']}%"],
        ["Class X", student["10th_board"], f"{student['10th_marks']}%"],
    ]
    edu_table = Table(edu_data, colWidths=[55*mm, 50*mm, 40*mm])
    edu_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_DARK),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, DIVIDER),
    ]))
    elements.append(edu_table)

    if int(student.get("backlogs_history", 0)) > 0:
        elements.append(Paragraph(
            f"Backlogs: {student['backlogs_history']} total, {student['active_backlogs']} active",
            styles["ItemDetail"]
        ))

    # --- SKILLS ---
    if skills:
        elements.append(Paragraph("TECHNICAL SKILLS", styles["SectionHeader"]))
        skill_groups = {}
        for s in skills:
            prof = s.get("proficiency", "Intermediate")
            if prof not in skill_groups:
                skill_groups[prof] = []
            skill_groups[prof].append(s["skill_name"])

        for prof in ["Advanced", "Intermediate", "Beginner"]:
            if prof in skill_groups:
                skill_str = ", ".join(skill_groups[prof])
                verified_count = sum(1 for s in skills if s.get("proficiency") == prof and s.get("verified"))
                label = f"<b>{prof}:</b> {skill_str}"
                if verified_count > 0:
                    label += f" <i>({verified_count} verified)</i>"
                elements.append(Paragraph(label, styles["ItemDetail"]))

    # --- CERTIFICATIONS ---
    if certs:
        elements.append(Paragraph("CERTIFICATIONS", styles["SectionHeader"]))
        for cert in certs:
            cert_line = f"<b>{cert['cert_name']}</b> — {cert['issuing_body']} ({cert['year_obtained']}) [{cert['tier']}]"
            elements.append(Paragraph(cert_line, styles["ItemDetail"]))

    # --- PROJECTS ---
    if projects:
        elements.append(Paragraph("PROJECTS", styles["SectionHeader"]))
        for proj in projects[:4]:  # Max 4 projects on resume
            title_line = f"<b>{proj['project_title']}</b> [{proj['complexity']}]"
            elements.append(Paragraph(title_line, styles["ItemTitle"]))

            detail_parts = [f"Tech: {proj['tech_stack']}"]
            detail_parts.append(f"Domain: {proj['domain']}")
            if str(proj.get("has_deployment", False)).lower() == "true":
                detail_parts.append("Deployed ✓")
            if str(proj.get("has_github", False)).lower() == "true":
                detail_parts.append("GitHub ✓")
            detail_parts.append(f"{proj['duration_weeks']} weeks | Team of {proj['team_size']}")

            elements.append(Paragraph(" | ".join(detail_parts), styles["ItemDetail"]))

    # --- INTERNSHIPS ---
    if internships:
        elements.append(Paragraph("INTERNSHIPS", styles["SectionHeader"]))
        for intern in internships:
            intern_line = (
                f"<b>{intern['role']}</b> at {intern['company_name']} "
                f"({intern['company_tier']}) — {intern['duration_months']} months "
                f"[{intern['mode']}] ({intern['year']})"
            )
            elements.append(Paragraph(intern_line, styles["ItemDetail"]))

    # --- RESEARCH PAPERS ---
    if papers:
        elements.append(Paragraph("RESEARCH PUBLICATIONS", styles["SectionHeader"]))
        for paper in papers:
            author_str = "First Author" if str(paper.get("is_first_author", False)).lower() == "true" else "Co-author"
            paper_line = (
                f"<b>{paper['title']}</b> — {paper['publication_venue']} "
                f"({paper['tier']}) [{author_str}] ({paper['year_published']})"
            )
            elements.append(Paragraph(paper_line, styles["ItemDetail"]))

    return elements


def generate_single_resume(student_id, students_df, certs_df, projects_df,
                           internships_df, papers_df, skills_df):
    """Generate PDF resume for a single student."""
    os.makedirs(RESUME_DIR, exist_ok=True)

    student = students_df[students_df["student_id"] == student_id].iloc[0].to_dict()
    certs = certs_df[certs_df["student_id"] == student_id].to_dict("records")
    projects = projects_df[projects_df["student_id"] == student_id].to_dict("records")
    internships = internships_df[internships_df["student_id"] == student_id].to_dict("records")
    papers = papers_df[papers_df["student_id"] == student_id].to_dict("records")
    skills = skills_df[skills_df["student_id"] == student_id].to_dict("records")

    filepath = os.path.join(RESUME_DIR, f"{student_id}_resume.pdf")

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    styles = get_styles()
    elements = build_resume_elements(student, certs, projects, internships, papers, skills, styles)
    doc.build(elements)

    return filepath


def generate_all_resumes(limit=None):
    """Generate resumes for all students (or a subset)."""
    print("📂 Loading data for resume generation...")
    students_df = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))
    certs_df = pd.read_csv(os.path.join(DATA_DIR, "certifications.csv"))
    projects_df = pd.read_csv(os.path.join(DATA_DIR, "projects.csv"))
    internships_df = pd.read_csv(os.path.join(DATA_DIR, "internships.csv"))
    papers_df = pd.read_csv(os.path.join(DATA_DIR, "research_papers.csv"))
    skills_df = pd.read_csv(os.path.join(DATA_DIR, "skills.csv"))

    student_ids = students_df["student_id"].tolist()
    if limit:
        student_ids = student_ids[:limit]

    total = len(student_ids)
    print(f"📄 Generating {total} resumes...")

    for i, sid in enumerate(student_ids):
        generate_single_resume(sid, students_df, certs_df, projects_df,
                               internships_df, papers_df, skills_df)
        if (i + 1) % 50 == 0 or (i + 1) == total:
            print(f"  → {i+1}/{total} resumes generated")

    print(f"✅ All {total} resumes saved to {RESUME_DIR}")


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    generate_all_resumes(limit=limit)
