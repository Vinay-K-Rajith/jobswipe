import os
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

from app.db.postgres_client import get_postgres_client  # noqa: E402

supabase = get_postgres_client()
DATA_DIR = Path(__file__).resolve().parent.parent / "datasets"


def seed_jobs():
    """Seed jobs from companies.csv - simplified version without checking for duplicates"""
    try:
        path = DATA_DIR / "companies.csv"
        if not path.exists():
            print(f"❌ {path} not found")
            return

        df = pd.read_csv(path)
        print(f"Found {len(df)} jobs in companies.csv\n")

        success = 0
        failed = 0
        
        for idx, row in df.iterrows():
            try:
                company_name = str(row.get("company_name", "") or "").strip()
                role = str(row.get("role", "") or "").strip()
                
                if not company_name or not role:
                    continue

                # Parse branches - format is "{Branch1,Branch2}"
                allowed_branches_str = str(row.get("allowed_branches", "") or "").strip()
                allowed_branches = [s.strip() for s in allowed_branches_str.replace("{", "").replace("}", "").split(",") if s.strip()]
                
                # Parse skills - format is "{Skill1,Skill2}"
                required_skills_str = str(row.get("required_skills", "") or "").strip()
                required_skills = [s.strip() for s in required_skills_str.replace("{", "").replace("}", "").split(",") if s.strip()]
                
                preferred_skills_str = str(row.get("preferred_skills", "") or "").strip()
                preferred_skills = [s.strip() for s in preferred_skills_str.replace("{", "").replace("}", "").split(",") if s.strip()]
                
                # Parse selection rounds
                selection_rounds_str = str(row.get("selection_rounds", "") or "").strip()
                selection_rounds = [s.strip() for s in selection_rounds_str.replace("{", "").replace("}", "").split(",") if s.strip()]
                
                # Insert job
                supabase.table("jobs").insert({
                    "company_name": company_name,
                    "role": role,
                    "allowed_branches": allowed_branches or [],
                    "min_cgpa": float(row.get("min_cgpa", 0.0) or 0.0),
                    "max_backlogs": int(row.get("max_backlogs", 0) or 0),
                    "batch_year": int(row.get("batch_year", 0) or 0),
                    "required_skills": required_skills or [],
                    "preferred_skills": preferred_skills or [],
                    "ctc": str(row.get("ctc", "") or "").strip(),
                    "location": str(row.get("location", "") or "").strip(),
                    "bond_years": int(row.get("bond_years", 0) or 0),
                    "selection_rounds": selection_rounds or [],
                    "job_description": str(row.get("job_description", "") or "").strip(),
                }).execute()
                
                print(f"✓ [{idx+1}/{len(df)}] {company_name} - {role}")
                success += 1
                
            except Exception as e:
                print(f"✗ [{idx+1}/{len(df)}] Error: {str(e)[:80]}")
                failed += 1

        print(f"\n✅ Jobs seeded! Success: {success}, Failed: {failed}")
    except Exception as e:
        print(f"❌ Jobs seeding failed: {e}")


if __name__ == "__main__":
    print("\n🌱 Starting job seeding...\n")
    seed_jobs()
    print("\n✅ Done!\n")
