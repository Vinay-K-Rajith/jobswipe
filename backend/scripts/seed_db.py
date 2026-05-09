import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client
from passlib.context import CryptContext
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
pwd = CryptContext(schemes=["bcrypt"])

_BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = _BASE_DIR / "data"
if not DATA_DIR.exists():
    DATA_DIR = _BASE_DIR / "datasets"


def seed_students():
    path = DATA_DIR / "students.csv"
    df = pd.read_csv(path)

    for _, row in df.iterrows():
        register_number = str(row.get("register_number") or "").strip()
        if not register_number:
            continue

        # if exists skip
        try:
            exists = supabase.table("students").select("id").eq("register_number", register_number).maybe_single().execute()
            if exists and exists.data:
                continue
        except Exception as e:
            pass

        try:
            supabase.table("students").insert({
                "register_number": register_number,
                "name": str(row.get("name", "") or "").strip(),
                "email": str(row.get("email", "") or "").strip(),
                "password_hash": str(row.get("password_hash", "hashed_password") or "hashed_password"),
                "college_name": str(row.get("college_name", "") or "").strip(),
                "branch": str(row.get("branch", "") or "").strip(),
                "cgpa": float(row.get("cgpa", 0.0) or 0.0),
                "active_backlogs": int(row.get("active_backlogs", 0) or 0),
                "batch_year": int(row.get("batch_year", 0) or 0),
                "skills": [s.strip() for s in str(row.get("skills", "") or "").replace("{", "").replace("}", "").split(",") if s.strip()],
                "certifications": [s.strip() for s in str(row.get("certifications", "") or "").replace("{", "").replace("}", "").split(",") if s.strip()],
                "projects": [s.strip() for s in str(row.get("projects", "") or "").replace("{", "").replace("}", "").split(",") if s.strip()],
            }).execute()
            print(f"  ✓ {register_number} - {row.get('name', '')}")
        except Exception as e:
            print(f"  ❌ Insert error for {register_number}: {e}")

    print("✓ Students seeded")


def seed_jobs():
    try:
        path = DATA_DIR / "companies.csv"
        df = pd.read_csv(path)

        for _, row in df.iterrows():
            company_name = str(row.get("company_name", "") or "").strip()
            role = str(row.get("role", "") or "").strip()
            if not company_name or not role:
                continue

            try:
                exists = supabase.table("jobs").select("id").eq("company_name", company_name).eq("role", role).maybe_single().execute()
                if exists and exists.data:
                    continue
            except:
                pass

            try:
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
                
                supabase.table("jobs").insert({
                    "company_name": company_name,
                    "role": role,
                    "allowed_branches": allowed_branches,
                    "min_cgpa": float(row.get("min_cgpa", 0.0) or 0.0),
                    "max_backlogs": int(row.get("max_backlogs", 0) or 0),
                    "batch_year": int(row.get("batch_year", 0) or 0),
                    "required_skills": required_skills,
                    "preferred_skills": preferred_skills,
                    "ctc": str(row.get("ctc", "") or "").strip(),
                    "location": str(row.get("location", "") or "").strip(),
                    "bond_years": int(row.get("bond_years", 0) or 0),
                    "selection_rounds": selection_rounds,
                    "job_description": str(row.get("job_description", "") or "").strip(),
                }).execute()
                print(f"  ✓ {company_name} - {role}")
            except Exception as e:
                print(f"  ❌ Insert error for {company_name} - {role}: {e}")

        print("✓ Jobs seeded")
    except Exception as e:
        print(f"❌ Jobs seeding failed: {e}")


def seed_skills_resources():
    try:
        # Seed skills_graph from CSV
        path = DATA_DIR / "skills_graph.csv"
        if path.exists():
            df = pd.read_csv(path)
            for _, row in df.iterrows():
                key = str(row.get("skill_name", "")).strip()
                if not key:
                    continue
                try:
                    exists = supabase.table("skills_graph").select("id").eq("skill_name", key).maybe_single().execute()
                    if exists and exists.data:
                        continue
                except:
                    pass
                try:
                    # Parse related_skills - format is "{Skill1,Skill2}"
                    related_skills_str = str(row.get("related_skills", "") or "").strip()
                    related_skills = [s.strip() for s in related_skills_str.replace("{", "").replace("}", "").split(",") if s.strip()]
                    
                    supabase.table("skills_graph").insert({
                        "skill_name": key,
                        "category": str(row.get("category", "") or "").strip(),
                        "related_skills": related_skills,
                        "difficulty_level": str(row.get("difficulty_level", "") or "").strip(),
                        "avg_learning_weeks": int(row.get("avg_learning_weeks", 0) or 0),
                        "industry_demand_score": float(row.get("industry_demand_score", 0.0) or 0.0),
                    }).execute()
                except Exception as e:
                    pass
            print("✓ skills_graph seeded")

        # Seed learning_resources from CSV
        path = DATA_DIR / "learning_resources.csv"
        if path.exists():
            df = pd.read_csv(path)
            for _, row in df.iterrows():
                try:
                    supabase.table("learning_resources").insert({
                        "skill_name": str(row.get("skill_name", "") or "").strip(),
                        "resource_type": str(row.get("resource_type", "") or "").strip(),
                        "title": str(row.get("title", "") or "").strip(),
                        "platform": str(row.get("platform", "") or "").strip(),
                        "link": str(row.get("link", "") or "").strip(),
                        "difficulty": str(row.get("difficulty", "") or "").strip(),
                        "duration_hours": int(row.get("duration_hours", 0) or 0),
                        "is_free": bool(row.get("is_free", True)),
                    }).execute()
                except Exception as e:
                    pass
            print("✓ learning_resources seeded")
    except Exception as e:
        print(f"❌ Skills/Resources seeding failed: {e}")


def seed_resumes():
    try:
        bucket = supabase.storage.from_("resumes")
        resume_dir = DATA_DIR / "dummy_resumes"
        if not resume_dir.is_dir():
            print("No dummy_resumes directory found")
            return

        count = 0
        for pdf_file in resume_dir.glob("*.pdf"):
            student_id = pdf_file.stem
            try:
                with open(pdf_file, "rb") as f:
                    contents = f.read()
                path = f"resumes/{student_id}.pdf"
                bucket.upload(path, contents, {"content-type": "application/pdf"})
                count += 1
            except Exception as e:
                print(f"Resume upload error for {student_id}: {e}")

        print(f"✓ {count} dummy resumes uploaded")
    except Exception as e:
        print(f"❌ Resume upload failed: {e}")


if __name__ == "__main__":
    print("\n🌱 Starting database seed...\n")
    seed_students()
    seed_jobs()
    seed_skills_resources()
    seed_resumes()
    print("\n✅ Seeding complete!\n")
