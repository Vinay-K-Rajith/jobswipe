"""AI Interview Prep — text-mode v1.

Multi-turn behavioral mock interview integrated into the JobSwipe stack
(FastAPI + Supabase, Groq for LLM turns). The interview flow is driven by a
deterministic question bank; Groq is used for optional follow-up probes and the
post-session feedback synthesis, both with graceful fallbacks.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.database import supabase
from app.routers.deps import get_current_user
from app.routers.swipe import execute_supabase
from app.services import interview_content as content
from app.services import interview_llm as llm

router = APIRouter(prefix="/interview", tags=["interview"])

MAX_SESSIONS_PER_DAY = 3
SECONDS_PER_QUESTION_ESTIMATE = 300


class CreateSessionRequest(BaseModel):
    target_role: str
    seniority: Optional[str] = None
    target_domain: Optional[str] = None
    interview_stage: Optional[str] = "first_round"
    resume_text: Optional[str] = None


class AnswerRequest(BaseModel):
    text: str


class RatingRequest(BaseModel):
    self_rating: str  # 'better' | 'same' | 'harder'


# ── helpers ──────────────────────────────────────────────────────────────────
def current_student_id(user: Dict[str, Any]) -> str:
    return str(user.get("student_id") or user.get("id") or user.get("register_number"))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_session(session_id: str, sid: str) -> Dict[str, Any]:
    result = execute_supabase(
        lambda: supabase.table("interview_sessions").select("*").eq("id", session_id).maybe_single()
    )
    session = result.data if result else None
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if str(session.get("student_id")) != sid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is not your session.")
    return session


def update_session(session_id: str, payload: Dict[str, Any]) -> None:
    execute_supabase(lambda: supabase.table("interview_sessions").update(payload).eq("id", session_id))


def append_turn(session_id: str, turn_index: int, speaker: str, contentstr: str, question_ref: Optional[str]) -> None:
    execute_supabase(
        lambda: supabase.table("interview_turns").insert({
            "session_id": session_id,
            "turn_index": turn_index,
            "speaker": speaker,
            "content": contentstr,
            "question_ref": question_ref,
        })
    )


def load_turns(session_id: str) -> List[Dict[str, Any]]:
    result = execute_supabase(
        lambda: supabase.table("interview_turns").select("*").eq("session_id", session_id).order("turn_index")
    )
    return result.data or []


def next_turn_index(session_id: str) -> int:
    return len(load_turns(session_id))


def build_profile_from_db(sid: str) -> Dict[str, Any]:
    """Best-effort structured profile from the student's existing JobSwipe data."""
    student_result = execute_supabase(
        lambda: supabase.table("students").select("full_name, department, cgpa, batch_year")
        .eq("student_id", sid).maybe_single()
    )
    student = (student_result.data if student_result else None) or {}
    skills = [
        str(r.get("skill_name")).strip()
        for r in (execute_supabase(lambda: supabase.table("skills").select("skill_name").eq("student_id", sid)).data or [])
        if r.get("skill_name")
    ]
    internships = execute_supabase(
        lambda: supabase.table("internships").select("company_name, role, duration_months").eq("student_id", sid).limit(5)
    ).data or []
    experiences = [
        {
            "company": r.get("company_name") or "",
            "role": r.get("role") or "",
            "duration_months": r.get("duration_months") or 0,
            "achievements": [],
        }
        for r in internships
    ]
    return {
        "current_role": student.get("department") and f"{student.get('department')} student" or "Student",
        "seniority": "entry",
        "domain": "",
        "experiences": experiences,
        "skills": skills,
        "thin_spots": [],
    }


def session_summary(session: Dict[str, Any]) -> Dict[str, Any]:
    plan = session.get("competency_plan") or {}
    sequence = session.get("question_sequence") or []
    return {
        "id": session["id"],
        "target_role": session.get("target_role"),
        "target_domain": session.get("target_domain"),
        "seniority": session.get("seniority"),
        "interview_stage": session.get("interview_stage"),
        "status": session.get("status"),
        "phase": session.get("phase"),
        "self_rating": session.get("self_rating"),
        "created_at": session.get("created_at"),
        "completed_at": session.get("completed_at"),
        "strengths": [content.competency_label(c) for c in plan.get("strengths", [])],
        "risks": [content.competency_label(c) for c in plan.get("risks", [])],
        "blind_spots": [content.competency_label(c) for c in plan.get("blind_spots", [])],
        "total_questions": len(sequence),
        "estimated_minutes": round(len(sequence) * SECONDS_PER_QUESTION_ESTIMATE / 60),
    }


def current_question(session: Dict[str, Any]) -> Optional[Dict[str, str]]:
    sequence = session.get("question_sequence") or []
    idx = session.get("current_index", 0)
    if 0 <= idx < len(sequence):
        return sequence[idx]
    return None


# ── endpoints ────────────────────────────────────────────────────────────────
@router.post("/sessions")
def create_session(req: CreateSessionRequest, user=Depends(get_current_user)):
    sid = current_student_id(user)

    day_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    todays = execute_supabase(
        lambda: supabase.table("interview_sessions").select("id")
        .eq("student_id", sid).gte("created_at", day_start.isoformat())
    ).data or []
    if len(todays) >= MAX_SESSIONS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit reached ({MAX_SESSIONS_PER_DAY} sessions/day). Try again tomorrow.",
        )

    profile = None
    if req.resume_text:
        profile = llm.structure_resume(req.resume_text)
    if not profile:
        profile = build_profile_from_db(sid)

    seniority = (req.seniority or profile.get("seniority") or "mid").strip().lower()
    competencies = content.competencies_for_role(req.target_role)
    gaps = content.analyze_gaps(profile, competencies)
    sequence = content.build_question_sequence(gaps)

    # Tailor each core question to the role + domain + candidate profile (one LLM
    # call, at creation time). Falls back to the bank question on any failure.
    core_indices = [i for i, step in enumerate(sequence) if step.get("type") == "core"]
    core_labels = [content.competency_label(sequence[i]["competency"]) for i in core_indices]
    tailored = llm.generate_questions(
        req.target_role, seniority, (req.target_domain or "").strip(), profile, core_labels
    )
    if tailored.get("opener") and sequence and sequence[0].get("type") == "opener":
        sequence[0]["question"] = tailored["opener"]
    for idx, question in zip(core_indices, tailored.get("questions") or []):
        sequence[idx]["question"] = question

    insert = execute_supabase(
        lambda: supabase.table("interview_sessions").insert({
            "student_id": sid,
            "target_role": req.target_role.strip(),
            "target_domain": (req.target_domain or "").strip() or None,
            "seniority": seniority,
            "interview_stage": req.interview_stage or "first_round",
            "structured_profile": profile,
            "competency_plan": gaps,
            "question_sequence": sequence,
            "phase": "pre_session",
            "status": "pre_session",
            "current_index": 0,
            "follow_up_used": False,
        })
    )
    session = insert.data[0] if insert and insert.data else None
    if not session:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to create session.")
    return session_summary(session)


@router.get("/sessions")
def list_sessions(user=Depends(get_current_user)):
    sid = current_student_id(user)
    rows = execute_supabase(
        lambda: supabase.table("interview_sessions").select("*")
        .eq("student_id", sid).order("created_at", desc=True).limit(50)
    ).data or []
    return {"sessions": [session_summary(r) for r in rows]}


@router.get("/sessions/{session_id}")
def get_session(session_id: str, user=Depends(get_current_user)):
    sid = current_student_id(user)
    session = load_session(session_id, sid)
    summary = session_summary(session)
    if session.get("status") == "active":
        cq = current_question(session)
        summary["current_question"] = cq["question"] if cq else None
        summary["current_competency"] = content.competency_label(cq["competency"]) if cq else None
    return summary


@router.post("/sessions/{session_id}/start")
def start_session(session_id: str, user=Depends(get_current_user)):
    sid = current_student_id(user)
    session = load_session(session_id, sid)

    if session.get("status") == "active":
        # idempotent resume: re-serve the current question
        cq = current_question(session)
        return {"session": session_summary(session), "first_question": cq["question"] if cq else None,
                "question_number": session.get("current_index", 0) + 1,
                "total_questions": len(session.get("question_sequence") or [])}
    if session.get("status") != "pre_session":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session already completed.")

    sequence = session.get("question_sequence") or []
    if not sequence:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Session has no questions.")

    opener = sequence[0]
    update_session(session_id, {
        "status": "active", "phase": "active",
        "current_index": 0, "follow_up_used": False,
        "started_at": now_utc().isoformat(),
    })
    append_turn(session_id, 0, "interviewer", opener["question"], opener.get("competency"))
    session["status"] = "active"
    session["phase"] = "active"
    return {
        "session": session_summary(session),
        "first_question": opener["question"],
        "question_number": 1,
        "total_questions": len(sequence),
    }


@router.post("/sessions/{session_id}/answer")
def answer(session_id: str, req: AnswerRequest, user=Depends(get_current_user)):
    sid = current_student_id(user)
    session = load_session(session_id, sid)
    if session.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not active.")

    answer_text = (req.text or "").strip()
    if not answer_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answer cannot be empty.")

    sequence = session.get("question_sequence") or []
    idx = session.get("current_index", 0)
    if idx >= len(sequence):
        return {"interviewer_turn": None, "done": True}

    cq = sequence[idx]
    competency = cq.get("competency")
    qtype = cq.get("type")

    # record candidate answer
    append_turn(session_id, next_turn_index(session_id), "candidate", answer_text, competency)

    # follow-up only on core questions, once per question
    if qtype == "core" and not session.get("follow_up_used"):
        decision = llm.decide_follow_up(cq["question"], competency, answer_text, session.get("structured_profile"))
        if decision.get("should_follow_up"):
            probe = decision["probe"]
            update_session(session_id, {"follow_up_used": True})
            append_turn(session_id, next_turn_index(session_id), "interviewer", probe, competency)
            return {
                "interviewer_turn": probe,
                "is_follow_up": True,
                "competency": content.competency_label(competency),
                "question_number": idx + 1,
                "total_questions": len(sequence),
                "done": False,
            }

    # advance to next question
    new_idx = idx + 1
    if new_idx >= len(sequence):
        update_session(session_id, {"current_index": new_idx, "follow_up_used": False})
        return {"interviewer_turn": None, "done": True}

    next_q = sequence[new_idx]
    ack = content.ack_for_index(new_idx)
    spoken = f"{ack} {next_q['question']}"
    update_session(session_id, {"current_index": new_idx, "follow_up_used": False})
    append_turn(session_id, next_turn_index(session_id), "interviewer", spoken, next_q.get("competency"))
    return {
        "interviewer_turn": spoken,
        "is_follow_up": False,
        "competency": content.competency_label(next_q.get("competency")) if next_q.get("competency") not in ("intro", "closing") else None,
        "question_number": new_idx + 1,
        "total_questions": len(sequence),
        "done": False,
    }


def _build_fallback_feedback(qa_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    per_q = []
    for pair in qa_pairs:
        if pair["competency"] in ("intro", "closing"):
            continue
        per_q.append({
            "question": pair["question"],
            "competency": content.competency_label(pair["competency"]),
            "what_happened": (pair["answer"][:240] + ("…" if len(pair["answer"]) > 240 else "")),
            "what_worked": "",
            "what_was_missing": "Detailed AI feedback was unavailable; review whether your answer had a clear situation, action, and measurable outcome.",
            "reconstructed_answer": "",
        })
    return {
        "overall_summary": "AI feedback synthesis was temporarily unavailable, so this is a basic summary. Re-run a session to get full coaching.",
        "headline_takeaway": "Make sure every answer ends with a concrete, measurable outcome.",
        "per_question_feedback": per_q,
        "recurring_patterns": [],
        "next_session_suggestion": "Try the session again shortly for full AI feedback.",
    }


def _qa_pairs(turns: List[Dict[str, Any]], sequence: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Pair each interviewer question turn with the candidate answer that follows it."""
    pairs: List[Dict[str, Any]] = []
    pending: Optional[Dict[str, Any]] = None
    for t in turns:
        if t["speaker"] == "interviewer":
            if pending:
                pairs.append(pending)
            pending = {"question": t["content"], "competency": t.get("question_ref") or "core", "answer": ""}
        elif t["speaker"] == "candidate" and pending is not None:
            pending["answer"] = (pending["answer"] + " " + t["content"]).strip()
    if pending:
        pairs.append(pending)
    return pairs


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: str, user=Depends(get_current_user)):
    sid = current_student_id(user)
    session = load_session(session_id, sid)

    # idempotent: return existing feedback
    existing = execute_supabase(
        lambda: supabase.table("interview_feedback").select("*").eq("session_id", session_id).maybe_single()
    )
    if existing and existing.data:
        return existing.data

    turns = load_turns(session_id)
    sequence = session.get("question_sequence") or []
    pairs = _qa_pairs(turns, sequence)

    feedback = llm.synthesize_feedback(
        session.get("structured_profile") or {},
        session.get("competency_plan") or {},
        turns,
    )
    if not feedback:
        feedback = _build_fallback_feedback(pairs)

    # attach code-computed answer metrics (deterministic, accurate) per question
    answer_pairs = [p for p in pairs if p["competency"] not in ("intro", "closing")]
    per_q = feedback.get("per_question_feedback") or []
    for i, item in enumerate(per_q):
        if i < len(answer_pairs):
            ans = answer_pairs[i]["answer"]
            item["filler_word_count"] = content.count_filler_words(ans)
            item["answer_word_count"] = content.word_count(ans)
            item["answer_too_long"] = content.word_count(ans) > 450
    feedback["per_question_feedback"] = per_q

    row = {
        "session_id": session_id,
        "overall_summary": str(feedback.get("overall_summary") or ""),
        "headline_takeaway": str(feedback.get("headline_takeaway") or ""),
        "per_question_feedback": per_q,
        "recurring_patterns": feedback.get("recurring_patterns") or [],
        "next_session_suggestion": str(feedback.get("next_session_suggestion") or ""),
    }
    saved = execute_supabase(lambda: supabase.table("interview_feedback").insert(row))
    update_session(session_id, {
        "status": "completed", "phase": "completed",
        "completed_at": now_utc().isoformat(),
    })
    return (saved.data[0] if saved and saved.data else row)


@router.get("/feedback/{session_id}")
def get_feedback(session_id: str, user=Depends(get_current_user)):
    sid = current_student_id(user)
    load_session(session_id, sid)  # ownership check
    result = execute_supabase(
        lambda: supabase.table("interview_feedback").select("*").eq("session_id", session_id).maybe_single()
    )
    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not ready.")
    return result.data


MAX_AUDIO_BYTES = 25 * 1024 * 1024  # Groq's transcription size cap


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Speech-to-text for a spoken answer (Groq Whisper). Voice mode only."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Audio too long.")
    text = llm.transcribe_audio(data, file.filename or "answer.webm")
    if not text:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not transcribe audio. Please try again.")
    return {"text": text}


@router.get("/sessions/{session_id}/transcript")
def get_transcript(session_id: str, user=Depends(get_current_user)):
    sid = current_student_id(user)
    load_session(session_id, sid)  # ownership check
    turns = load_turns(session_id)
    return {
        "turns": [
            {"speaker": t.get("speaker"), "content": t.get("content"), "turn_index": t.get("turn_index")}
            for t in turns
        ]
    }


@router.post("/sessions/{session_id}/rating")
def set_rating(session_id: str, req: RatingRequest, user=Depends(get_current_user)):
    sid = current_student_id(user)
    load_session(session_id, sid)
    if req.self_rating not in ("better", "same", "harder"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid rating.")
    update_session(session_id, {"self_rating": req.self_rating})
    return {"success": True}
