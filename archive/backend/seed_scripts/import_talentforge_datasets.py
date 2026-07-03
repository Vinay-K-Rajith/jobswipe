from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
SOURCE_DIR = Path(r"c:\Users\Asus\OneDrive\Desktop\TalentForge")

load_dotenv(ENV_PATH)


def split_list(value):
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def clean_text(value, fallback=""):
    if pd.isna(value):
        return fallback
    return str(value).strip()


def salary_lpa(value):
    if pd.isna(value):
        return None
    amount = float(value)
    return round(amount / 100000, 2)


def first_role(value):
    roles = split_list(value)
    return roles[0] if roles else "Intern"


def normalize_student_id(value):
    raw = clean_text(value)
    raw = re.sub(r"\.0$", "", raw)
    return f"TF{raw}"


def build_job_records(path, job_type):
    df = pd.read_excel(path)
    rows = []
    for _, row in df.iterrows():
        company_name = clean_text(row["com_name"], "Company")
        role_title = first_role(row["job_title"])
        salary = float(row["salary"])
        salary_text = f"Rs {int(salary):,} {'/ month' if job_type == 'internship' else '/ year'}"
        size = clean_text(row["company_size"], "company")
        level = clean_text(row["student_rank"], "all")
        startup = bool(int(row["is_startup"]))
        job_type_label = "Internship" if job_type == "internship" else "Full-time"
        rows.append({
            "company_name": company_name,
            "role": role_title,
            "role_title": role_title,
            "industry": clean_text(row["industry"], "Technology"),
            "location": clean_text(row["location"], "India"),
            "remote_policy": "hybrid",
            "allowed_branches": [],
            "allowed_departments": [],
            "min_cgpa": 0,
            "max_backlogs": 0,
            "required_skills": split_list(row["prerequisites"]),
            "preferred_skills": [],
            "ctc": salary_text,
            "package_lpa": salary_lpa(row["salary"]) if job_type == "fulltime" else None,
            "bond_years": 0,
            "selection_rounds": [job_type_label, f"{size.title()} company", f"{level.title()} candidates"],
            "interview_timeline": f"{job_type_label} opening for {level} candidates.",
            "mentorship": f"{'Startup' if startup else 'Established'} {size} company. Candidate level: {level}.",
            "highlight_line": f"{job_type_label} | {salary_text} | {size.title()} | {level.title()}",
            "job_description": clean_text(row["job_description"], f"{company_name} is hiring for {role_title}."),
            "is_active": True,
        })
    return rows


def build_student_records(path):
    df = pd.read_excel(path)
    rows = []
    for _, row in df.iterrows():
        student_id = normalize_student_id(row["student_id"])
        job_type = clean_text(row["preferred_job_type"], "role")
        location = clean_text(row["preferred_job_location"], "India")
        role = clean_text(row["preferred_role"], "role")
        size = clean_text(row["preferred_job_size"], "company")
        category = clean_text(row["Category"], "all")
        expected_pa = 0 if pd.isna(row["expected_salary_pa"]) else int(row["expected_salary_pa"])
        expected_pm = 0 if pd.isna(row["expected_salary_pm"]) else int(row["expected_salary_pm"])
        expectation = expected_pm if job_type.lower() == "internship" else expected_pa
        expectation_label = f"Rs {expectation:,} {'/ month' if job_type.lower() == 'internship' else '/ year'}" if expectation else "Open"
        rows.append({
            "student_id": student_id,
            "register_number": student_id,
            "full_name": clean_text(row["student_name"], student_id),
            "name": clean_text(row["student_name"], student_id),
            "email": f"{student_id.lower()}@srmist.edu.in",
            "gender": None,
            "department": category.upper(),
            "branch": category,
            "college_name": f"Preference: {job_type} | {role} | {location} | {size} | {expectation_label}",
            "cgpa": float(row["CGPA"]),
            "active_backlogs": 0,
            "year_of_study": int(row["year"]),
            "batch_year": 2024 + int(row["year"]),
            "skills": split_list(row["skills"]),
            "certifications": [f"Preferred role: {role}", f"Preferred type: {job_type}", f"Expected: {expectation_label}"],
            "projects": [f"Preferred location: {location}", f"Preferred company size: {size}"],
        })
    deduped = {}
    for row in rows:
        deduped[row["student_id"]] = row
    return list(deduped.values())


def build_skill_records(path):
    df = pd.read_excel(path)
    records = []
    seen = set()
    for _, row in df.iterrows():
        sid = normalize_student_id(row["student_id"])
        proficiency = "Advanced" if clean_text(row["Category"]).lower() == "advanced" else "Intermediate"
        for skill in split_list(row["skills"]):
            key = (sid, skill.lower())
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "student_id": sid,
                "skill_name": skill,
                "proficiency": proficiency,
                "verified": True,
            })
    return records


def main():
    from app.db.postgres_client import get_postgres_client
    client = get_postgres_client()

    fulltime_jobs = build_job_records(SOURCE_DIR / "companydataset.xlsx", "fulltime")
    internship_jobs = build_job_records(SOURCE_DIR / "internshipdataset.xlsx", "internship")
    students = build_student_records(SOURCE_DIR / "studentsdataset.xlsx")
    skills = build_skill_records(SOURCE_DIR / "studentsdataset.xlsx")

    existing_jobs = client.table("jobs").select("company_name,role,ctc").execute().data or []
    existing_keys = {(row.get("company_name"), row.get("role"), row.get("ctc")) for row in existing_jobs}
    jobs_to_insert = [
        row for row in (fulltime_jobs + internship_jobs)
        if (row["company_name"], row["role"], row["ctc"]) not in existing_keys
    ]

    job_result = client.table("jobs").insert(jobs_to_insert).execute() if jobs_to_insert else None
    student_result = client.table("students").upsert(students, on_conflict="student_id").execute()
    existing_skills = client.table("skills").select("student_id,skill_name").like("student_id", "TF%").execute().data or []
    existing_skill_keys = {(row.get("student_id"), str(row.get("skill_name")).lower()) for row in existing_skills}
    skills_to_insert = [
        row for row in skills
        if (row["student_id"], row["skill_name"].lower()) not in existing_skill_keys
    ]
    skill_result = client.table("skills").insert(skills_to_insert).execute() if skills_to_insert else None

    print(f"Inserted {len((job_result.data if job_result else []) or [])} TalentForge jobs/internships.")
    print(f"Upserted {len(student_result.data or [])} TalentForge students.")
    print(f"Inserted {len((skill_result.data if skill_result else []) or [])} TalentForge skills.")


if __name__ == "__main__":
    main()
