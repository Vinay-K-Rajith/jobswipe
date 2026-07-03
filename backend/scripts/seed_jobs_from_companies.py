from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "companies.csv"

load_dotenv(ENV_PATH)


def split_csv(value):
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def main():
    from app.db.postgres_client import get_postgres_client
    client = get_postgres_client()
    df = pd.read_csv(DATA_PATH)

    jobs = []
    for _, row in df.iterrows():
        role_title = str(row.get("role_offered") or "Intern").strip()
        company_name = str(row.get("company_name") or "Company").strip()
        jobs.append({
            "company_name": company_name,
            "role": role_title,
            "role_title": role_title,
            "industry": None if pd.isna(row.get("industry")) else str(row.get("industry")),
            "location": "India",
            "remote_policy": "hybrid",
            "allowed_branches": split_csv(row.get("allowed_departments")),
            "allowed_departments": split_csv(row.get("allowed_departments")),
            "min_cgpa": float(row.get("min_cgpa") or 0),
            "max_backlogs": int(row.get("max_active_backlogs") or 0),
            "required_skills": split_csv(row.get("required_skills")),
            "preferred_skills": split_csv(row.get("preferred_skills")),
            "ctc": f"{row.get('package_lpa')} LPA" if not pd.isna(row.get("package_lpa")) else "",
            "package_lpa": None if pd.isna(row.get("package_lpa")) else float(row.get("package_lpa")),
            "bond_years": int(row.get("bond_years") or 0),
            "selection_rounds": ["Screening", "Technical Interview", "Final Interview"],
            "interview_timeline": "Screening -> technical interview -> final interview",
            "mentorship": "Team mentorship during onboarding and project work.",
            "highlight_line": f"{role_title} opportunity at {company_name}",
            "job_description": f"{company_name} is hiring for {role_title}.",
            "is_active": True,
        })

    existing = client.table("jobs").select("id").limit(1).execute()
    if existing.data:
        print("Jobs table already has data; skipping insert.")
        return

    result = client.table("jobs").insert(jobs).execute()
    print(f"Inserted {len(result.data or [])} jobs.")


if __name__ == "__main__":
    main()
