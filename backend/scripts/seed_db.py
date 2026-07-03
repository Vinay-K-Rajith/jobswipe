import os
import pandas as pd
from dotenv import load_dotenv
from passlib.context import CryptContext
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

from app.db.postgres_client import get_postgres_client  # noqa: E402

supabase = get_postgres_client()
pwd = CryptContext(schemes=["bcrypt"])

_BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = _BASE_DIR / "data"
if not DATA_DIR.exists():
    DATA_DIR = _BASE_DIR / "datasets"


def seed_students():
    path = DATA_DIR / "students.csv"
    df = pd.read_csv(path)

    for _, row in df.iterrows():
        # Support both canonical (student_id) and legacy (register_number) CSV formats
        student_id = str(row.get("student_id") or row.get("register_number") or "").strip()
        if not student_id:
            continue

        # if exists, skip
        try:
            exists = supabase.table("students").select("student_id").eq("student_id", student_id).maybe_single().execute()
            if exists and exists.data:
                continue
        except Exception:
            pass

        try:
            # Build insert payload using only columns that exist in the DB schema
            full_name = str(row.get("full_name") or row.get("name") or "").strip()
            payload = {
                "student_id": student_id,
                "full_name": full_name,
                "name": full_name,
                "department": str(row.get("department") or row.get("branch") or "").strip(),
                "cgpa": float(row.get("cgpa") or 0.0),
                "active_backlogs": int(row.get("active_backlogs") or 0),
                "year_of_study": int(row.get("year_of_study") or 0),
                "register_number": str(row.get("register_number") or student_id),
            }
            # Optional columns
            if row.get("gender"):
                payload["gender"] = str(row.get("gender")).strip()
            if row.get("batch_year"):
                payload["batch_year"] = int(row.get("batch_year") or 0)
            if row.get("10th_marks"):
                payload["10th_marks"] = float(row.get("10th_marks") or 0)
            if row.get("10th_board"):
                payload["10th_board"] = str(row.get("10th_board")).strip()
            if row.get("12th_marks"):
                payload["12th_marks"] = float(row.get("12th_marks") or 0)
            if row.get("12th_board"):
                payload["12th_board"] = str(row.get("12th_board")).strip()
            if row.get("backlogs_history"):
                payload["backlogs_history"] = int(row.get("backlogs_history") or 0)
            if row.get("email"):
                payload["email"] = str(row.get("email")).strip()

            supabase.table("students").insert(payload).execute()
            print(f"  \u2713 {student_id} - {full_name}")
        except Exception as e:
            print(f"  \u274c Insert error for {student_id}: {e}")

    print("\u2713 Students seeded")


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
                    "role_title": role,
                    "allowed_branches": allowed_branches,
                    "allowed_departments": allowed_branches,
                    "min_cgpa": float(row.get("min_cgpa", 0.0) or 0.0),
                    "max_active_backlogs": int(row.get("max_backlogs", row.get("max_active_backlogs", 999)) or 999),
                    "required_skills": required_skills,
                    "preferred_skills": preferred_skills,
                    "ctc": str(row.get("ctc", "") or "").strip(),
                    "location": str(row.get("location", "") or "").strip(),
                    "bond_years": int(row.get("bond_years", 0) or 0),
                    "selection_rounds": selection_rounds,
                    "job_description": str(row.get("job_description", "") or "").strip(),
                }).execute()
                print(f"  \u2713 {company_name} - {role}")
            except Exception as e:
                print(f"  \u274c Insert error for {company_name} - {role}: {e}")

        print("✓ Jobs seeded")
    except Exception as e:
        print(f"❌ Jobs seeding failed: {e}")


def seed_skills_resources():
    try:
        # Seed skills_graph from CSV
        # DB schema: (id, skill_name, avg_learning_weeks, difficulty_level, prerequisites)
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
                    supabase.table("skills_graph").insert({
                        "skill_name": key,
                        "difficulty_level": str(row.get("difficulty_level", "Intermediate") or "Intermediate").strip(),
                        "avg_learning_weeks": int(row.get("avg_learning_weeks", 3) or 3),
                    }).execute()
                except Exception as e:
                    pass
            print("✓ skills_graph seeded")
        else:
            print("  skills_graph.csv not found, skipping")

        # Seed learning_resources from CSV
        # DB schema: (id, skill_name, title, url, resource_type, estimated_hours)
        path = DATA_DIR / "learning_resources.csv"
        if path.exists():
            df = pd.read_csv(path)
            for _, row in df.iterrows():
                try:
                    # Map CSV fields to actual DB columns
                    url = str(row.get("link", "") or row.get("url", "") or "").strip()
                    estimated_hours = int(row.get("duration_hours", 0) or row.get("estimated_hours", 0) or 0)
                    supabase.table("learning_resources").insert({
                        "skill_name": str(row.get("skill_name", "") or "").strip(),
                        "resource_type": str(row.get("resource_type", "") or "").strip(),
                        "title": str(row.get("title", "") or "").strip(),
                        "url": url,
                        "estimated_hours": estimated_hours,
                    }).execute()
                except Exception as e:
                    pass
            print("✓ learning_resources seeded")
        else:
            print("  learning_resources.csv not found, skipping")
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
