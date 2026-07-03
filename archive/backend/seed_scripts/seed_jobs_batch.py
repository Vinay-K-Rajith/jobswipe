import csv
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import supabase

def seed_jobs_batch():
    """Seed jobs table with batch inserts (efficient and fast)"""
    csv_path = Path(__file__).parent.parent / "datasets" / "companies.csv"
    
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return
    
    print(f"🌱 Reading jobs from {csv_path}...")
    
    jobs_batch = []
    batch_size = 500
    total_inserted = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for idx, row in enumerate(reader, 1):
                try:
                    job = {
                        "company_name": row.get("company_name", "").strip(),
                        "role": row.get("role", "").strip(),
                        "allowed_branches": [b.strip() for b in row.get("allowed_branches", "").split(",") if b.strip()],
                        "min_cgpa": float(row.get("min_cgpa", 0)) if row.get("min_cgpa") else 0.0,
                        "max_backlogs": int(row.get("max_backlogs", 0)) if row.get("max_backlogs") else 0,
                        "batch_year": int(row.get("batch_year", 2025)) if row.get("batch_year") else 2025,
                        "required_skills": [s.strip() for s in row.get("required_skills", "").split(",") if s.strip()],
                        "preferred_skills": [s.strip() for s in row.get("preferred_skills", "").split(",") if s.strip()],
                        "ctc": row.get("ctc", "Not specified").strip(),
                        "location": row.get("location", "Remote").strip(),
                        "bond_years": int(row.get("bond_years", 0)) if row.get("bond_years") else 0,
                        "selection_rounds": [r.strip() for r in row.get("selection_rounds", "").split(",") if r.strip()],
                        "job_description": row.get("job_description", "").strip(),
                    }
                    jobs_batch.append(job)
                    
                    # Insert when batch is full
                    if len(jobs_batch) >= batch_size:
                        result = supabase.table("jobs").insert(jobs_batch).execute()
                        inserted = len(result.data) if result.data else 0
                        total_inserted += inserted
                        print(f"✅ Batch {idx // batch_size}: Inserted {inserted} jobs (Total: {total_inserted})")
                        jobs_batch = []
                
                except Exception as e:
                    print(f"⚠️  Row {idx} error: {str(e)[:100]}")
                    continue
        
        # Insert remaining jobs
        if jobs_batch:
            result = supabase.table("jobs").insert(jobs_batch).execute()
            inserted = len(result.data) if result.data else 0
            total_inserted += inserted
            print(f"✅ Final batch: Inserted {inserted} jobs")
        
        print(f"\n🎉 Success! Total jobs inserted: {total_inserted}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    seed_jobs_batch()
