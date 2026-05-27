from fastapi import APIRouter, Depends
from app.database import supabase
from app.services.eligibility import get_eligible_jobs
from app.services.recommender import get_recommended_jobs
from app.services.bias_score import compute_bias_adjusted_score
from app.routers.deps import get_current_user
from app.routers.swipe import blended_pair_score

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/all")
def get_all_jobs():
    """Get all jobs (public endpoint)"""
    all_jobs = supabase.table("jobs").select("*").execute().data or []
    return all_jobs


@router.get("/eligible/{student_id}")
def get_eligible_jobs_for_student(student_id: str, user=Depends(get_current_user)):
    if user["id"] != student_id:
        return []

    student_result = supabase.table("students").select("*").eq("id", student_id).maybe_single().execute()
    student = student_result.data if student_result else None
    if not student:
        return {"message": "Student profile not found", "eligible_jobs": []}
    
    # Check if profile is complete
    if not all([student.get("branch"), student.get("cgpa") is not None, student.get("batch_year")]):
        return {"message": "Please complete your profile first", "eligible_jobs": []}
    
    # DEBUG: Log student profile
    print(f"🔍 DEBUG: Student {student_id}")
    print(f"   Branch: {student.get('branch')} (type: {type(student.get('branch'))})")
    print(f"   CGPA: {student.get('cgpa')} (type: {type(student.get('cgpa'))})")
    print(f"   Batch Year: {student.get('batch_year')} (type: {type(student.get('batch_year'))})")
    print(f"   Active Backlogs: {student.get('active_backlogs')} (type: {type(student.get('active_backlogs'))})")
    
    all_jobs = supabase.table("jobs").select("*").execute().data or []
    print(f"   Total jobs in database: {len(all_jobs)}")
    
    # Sample a job to check structure
    if all_jobs:
        sample = all_jobs[0]
        print(f"   Sample job: {sample.get('role')} @ {sample.get('company_name')}")
        print(f"   min_cgpa: {sample.get('min_cgpa')} (type: {type(sample.get('min_cgpa'))})")
        print(f"   allowed_branches: {sample.get('allowed_branches')}")
        print(f"   batch_year: {sample.get('batch_year')}")

    # Get eligible jobs based on criteria (no bias)
    eligible = get_eligible_jobs(student, all_jobs)
    
    # Apply bias reduction scoring to eligible jobs
    for job in eligible:
        bias_score = compute_bias_adjusted_score(student, job)
        job["bias_score"] = bias_score
    
    print(f"   Eligible jobs found: {len(eligible)}")
    
    # Return with bias scores
    return {"eligible_jobs": eligible}


@router.get("/recommend/{student_id}")
def get_recommendations(student_id: str, user=Depends(get_current_user)):
    if user["id"] != student_id:
        return []

    student_result = supabase.table("students").select("*").eq("id", student_id).maybe_single().execute()
    student = student_result.data if student_result else None
    if not student:
        return {"message": "Student not found", "recommended_jobs": []}
    
    # DEBUG: Log student skills
    student_skills = student.get("skills") or []
    print(f"🔍 Cross-domain recommendation for {student_id}:")
    print(f"   Student skills extracted: {len(student_skills)} skills")
    if student_skills:
        print(f"   Skills: {student_skills[:10]}")  # Show first 10
    
    all_jobs = supabase.table("jobs").select("*").execute().data or []
    eligible = get_eligible_jobs(student, all_jobs)
    eligible_ids = {job.get("id") for job in eligible}
    
    print(f"   Eligible jobs: {len(eligible)}")
    print(f"   Cross-domain candidates: {len(all_jobs) - len(eligible)}")
    
    recommendations = get_recommended_jobs(student, all_jobs, eligible_ids, score_pair=blended_pair_score)
    
    print(f"   Recommendations found: {len(recommendations)}")
    if recommendations:
        print(f"   Top recommendation: {recommendations[0].get('role')} @ {recommendations[0].get('company_name')} (match: {recommendations[0].get('skill_match')})")
    
    return {"recommended_jobs": recommendations}
