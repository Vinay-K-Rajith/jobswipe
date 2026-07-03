from fastapi import APIRouter, HTTPException, Depends
from app.database import supabase
from app.services.roadmap import generate_roadmap
from app.routers.deps import get_current_user

router = APIRouter(prefix="/upskill", tags=["upskill"])


@router.get("/{student_id}/{job_id}")
def get_upskill_plan(student_id: str, job_id: str, user=Depends(get_current_user)):
    # user may have student_id or id depending on the DB record
    user_sid = str(user.get("student_id") or user.get("id") or user.get("register_number") or "")
    if user_sid != student_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    student_result = supabase.table("students").select("*").eq("student_id", student_id).maybe_single().execute()
    student = student_result.data if student_result else None

    job_result = supabase.table("jobs").select("*").eq("id", job_id).maybe_single().execute()
    job = job_result.data if job_result else None

    if not student or not job:
        raise HTTPException(status_code=404, detail="Student or job not found")

    roadmap = generate_roadmap(student, job, supabase)
    return roadmap
