from pathlib import Path
import re

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SOURCE_DIR = Path(r"c:\Users\Asus\OneDrive\Desktop\TalentForge")


def split_list(value):
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def clean_text(value, fallback=""):
    if pd.isna(value):
        return fallback
    return str(value).strip()


def normalize_student_id(value):
    raw = re.sub(r"\.0$", "", clean_text(value))
    return f"TF{raw}"


def complexity_for_rank(rank):
    normalized = clean_text(rank, "all").lower()
    if normalized == "advanced":
        return "Advanced"
    if normalized == "intermediate":
        return "Intermediate"
    return "Basic"


def tier_for_company(size, startup):
    if bool(int(startup)):
        return "Startup"
    normalized = clean_text(size, "").lower()
    if normalized == "large":
        return "Tier1"
    if normalized == "midsize":
        return "Tier2"
    return "Tier3"


def salary_lpa(value, job_type):
    amount = 0 if pd.isna(value) else float(value)
    if job_type == "internship":
        return round((amount * 12) / 100000, 2)
    return round(amount / 100000, 2)


def first_role(value):
    roles = split_list(value)
    return roles[0] if roles else "Role"


def build_company_rows(path, prefix, job_type):
    df = pd.read_excel(path)
    rows = []
    for idx, row in df.iterrows():
        required = split_list(row["prerequisites"])
        location = clean_text(row["location"], "India")
        rank = clean_text(row["student_rank"], "all")
        size = clean_text(row["company_size"], "company")
        salary = int(float(row["salary"]))
        role = first_role(row["job_title"])
        label = "Internship" if job_type == "internship" else "Full-time"
        rows.append({
            "company_id": f"{prefix}{idx + 1:03d}",
            "company_name": clean_text(row["com_name"], "Company"),
            "industry": clean_text(row["industry"], "Technology"),
            "tier": tier_for_company(row["company_size"], row["is_startup"]),
            "min_cgpa": 8.5 if rank.lower() == "advanced" else 7.0 if rank.lower() == "intermediate" else 0.0,
            "min_10th": 0.0,
            "min_12th": 0.0,
            "max_active_backlogs": 0,
            "allowed_departments": "CSE,IT,AIML,AIDS",
            "required_skills": ",".join(required),
            "preferred_skills": "",
            "min_internship_months": 0.0,
            "internship_tier_preference": "Any",
            "min_projects": 0,
            "project_complexity_min": complexity_for_rank(rank),
            "requires_research_paper": False,
            "cert_tier_required": "None",
            "role_offered": f"{role} ({label}, {location}, {size}, Rs {salary:,} {'/ month' if job_type == 'internship' else '/ year'})",
            "package_lpa": salary_lpa(row["salary"], job_type),
            "bond_years": 0,
        })
    return rows


def build_student_rows(path):
    df = pd.read_excel(path)
    students = []
    skills = []
    for _, row in df.iterrows():
        sid = normalize_student_id(row["student_id"])
        if any(student["student_id"] == sid for student in students):
            continue
        students.append({
            "student_id": sid,
            "full_name": clean_text(row["student_name"], sid),
            "gender": "Prefer not to say",
            "department": clean_text(row["Category"], "all").upper(),
            "10th_marks": 0.0,
            "10th_board": "NA",
            "12th_marks": 0.0,
            "12th_board": "NA",
            "cgpa": float(row["CGPA"]),
            "backlogs_history": 0,
            "active_backlogs": 0,
            "year_of_study": int(row["year"]),
        })
        for skill in split_list(row["skills"]):
            skills.append({
                "student_id": sid,
                "skill_name": skill,
                "proficiency": "Advanced" if clean_text(row["Category"]).lower() == "advanced" else "Intermediate",
                "verified": True,
            })
    return students, skills


def upsert_csv(path, key_columns, new_rows):
    current = pd.read_csv(path)
    incoming = pd.DataFrame(new_rows)
    combined = pd.concat([current, incoming], ignore_index=True)
    combined = combined.drop_duplicates(subset=key_columns, keep="last")
    combined.to_csv(path, index=False)
    return len(current), len(combined)


def main():
    company_rows = build_company_rows(SOURCE_DIR / "companydataset.xlsx", "TFJ", "fulltime")
    internship_rows = build_company_rows(SOURCE_DIR / "internshipdataset.xlsx", "TFI", "internship")
    student_rows, skill_rows = build_student_rows(SOURCE_DIR / "studentsdataset.xlsx")

    before, after = upsert_csv(DATA_DIR / "companies.csv", ["company_id"], company_rows + internship_rows)
    print(f"companies.csv: {before} -> {after}")

    before, after = upsert_csv(DATA_DIR / "students.csv", ["student_id"], student_rows)
    print(f"students.csv: {before} -> {after}")

    before, after = upsert_csv(DATA_DIR / "skills.csv", ["student_id", "skill_name"], skill_rows)
    print(f"skills.csv: {before} -> {after}")


if __name__ == "__main__":
    main()
