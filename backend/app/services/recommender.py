from typing import Callable, Optional


def baseline_overlap_score(student: dict, job: dict) -> tuple[float, str]:
    student_skills = set(s.lower().strip() for s in (student.get("skills") or []) if s)
    student_branch = str(student.get("branch") or student.get("department") or "").lower()
    job_branch = job.get("allowed_branches") or job.get("allowed_departments") or []

    if student_skills:
        required = set(s.lower().strip() for s in (job.get("required_skills") or []) if s)
        preferred = set(s.lower().strip() for s in (job.get("preferred_skills") or []) if s)
        all_job_skills = required | preferred
        if not all_job_skills:
            return 0.0, "No comparable skills listed"
        overlap = len(student_skills & all_job_skills) / len(all_job_skills)
        return overlap, f"{int(overlap * 100)}% skill overlap"

    if job_branch and student_branch and student_branch not in [str(b).lower() for b in job_branch]:
        return 0.5, "Cross-domain opportunity"

    return 0.0, "No recommendation signal"


def get_recommended_jobs(
    student: dict,
    all_jobs: list,
    eligible_job_ids: set,
    score_pair: Optional[Callable[[dict, dict], tuple[float, dict]]] = None,
    min_score: float = 0.15,
) -> list:
    """
    Find cross-domain (non-eligible but relevant) job recommendations.

    Strategy:
    1. Exclude jobs student is already eligible for
    2. Prefer the production student-job pair scorer if supplied
    3. Fallback to a transparent baseline overlap score
    4. Limit to top 10 by recommendation score
    """
    recommendations = []

    for job in all_jobs:
        if job.get("id") in eligible_job_ids:
            continue

        breakdown = {}
        source = "baseline_overlap"
        if score_pair:
            score, breakdown = score_pair(student, job)
            reason = "Blended student-job fit score"
            source = "blended_pair_score"
        else:
            score, reason = baseline_overlap_score(student, job)

        if score >= min_score:
            recommendations.append({
                **job,
                "skill_match": round(score, 3),
                "recommendation_score": round(score, 3),
                "match_reason": reason,
                "recommender_source": source,
                "match_breakdown": breakdown,
            })

    recommendations = sorted(recommendations, key=lambda x: x["recommendation_score"], reverse=True)[:10]

    return recommendations
