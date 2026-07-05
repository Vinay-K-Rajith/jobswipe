"""Groq-backed LLM helpers for the interview prep feature.

Three calls, all designed to degrade gracefully (never raise into the request
flow): resume structuring, the in-session follow-up decision, and the
post-session feedback synthesis. The interview itself runs on the deterministic
question bank, so an LLM outage only costs richness, not the session.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from groq import Groq

from app.services import interview_content as content

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"


STT_MODEL = "whisper-large-v3-turbo"


def _client() -> Groq:
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def transcribe_audio(data: bytes, filename: str = "answer.webm") -> str:
    """Transcribe candidate audio with Groq Whisper. Returns '' on failure."""
    if not data:
        return ""
    try:
        result = _client().audio.transcriptions.create(
            file=(filename, data),
            model=STT_MODEL,
            response_format="json",
            language="en",
        )
        text = getattr(result, "text", None)
        if text is None and isinstance(result, str):
            text = result
        return (text or "").strip()
    except Exception as exc:
        logger.warning("Groq transcription failed: %s", exc)
        return ""


def _strip_fences(text: str) -> str:
    text = (text or "").strip()
    # remove ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json(text: str) -> Optional[Any]:
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # last resort: grab the outermost {...} or [...] block
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            return None
    return None


def _groq_json(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float = 0.4) -> Optional[Any]:
    """Single Groq call returning parsed JSON, or None on any failure."""
    try:
        response = _client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        return _extract_json(raw)
    except Exception as exc:
        logger.warning("Groq interview call failed: %s", exc)
        return None


# ── 1. Resume structuring ────────────────────────────────────────────────────
_RESUME_SYSTEM = (
    "You are a resume parser. Extract structured data from the resume text and "
    "return ONLY valid JSON (a single object), no preamble, no markdown. Schema: "
    '{"current_role": string, "seniority": "entry"|"mid"|"senior"|"lead", '
    '"domain": string, "experiences": [{"company": string, "role": string, '
    '"duration_months": number, "achievements": [string]}], "skills": [string], '
    '"thin_spots": [string]}. thin_spots = areas vague, missing, or '
    "underdeveloped for the candidate's seniority. Never invent information."
)


def structure_resume(resume_text: str) -> Optional[Dict[str, Any]]:
    if not (resume_text or "").strip():
        return None
    data = _groq_json(
        _RESUME_SYSTEM,
        f"Resume text:\n{resume_text[:8000]}",
        max_tokens=1500,
        temperature=0.0,
    )
    if isinstance(data, dict):
        # normalize expected fields
        data.setdefault("current_role", "")
        data.setdefault("seniority", "mid")
        data.setdefault("domain", "")
        data.setdefault("experiences", [])
        data.setdefault("skills", [])
        data.setdefault("thin_spots", [])
        return data
    return None


# ── 1b. Tailored question set (generated once at session creation) ───────────
_QUESTIONS_SYSTEM = (
    "You are an expert interviewer writing a tailored behavioral interview. Given a "
    "candidate's background and a target role, produce:\n"
    "1. an OPENER: a warm opening question inviting the candidate to walk through their "
    "background and what draws them to this specific role, grounded in their domain/stack "
    "(not a 'tell me about a time' question).\n"
    "2. one behavioral QUESTION for each competency provided. Each question MUST:\n"
    "- assess that specific competency;\n"
    "- be grounded in the candidate's actual background and the target role/domain — "
    "reference their stack, domain, or experience where it reads naturally;\n"
    "- be a single open behavioral question (\"Tell me about a time…\" / \"Describe…\");\n"
    "- be concise (one or two sentences), not generic, not multi-part.\n"
    "Return ONLY JSON: {\"opener\": string, \"questions\": [string, ...]} with exactly one "
    "question per competency, in the same order as given. No preamble, no markdown."
)


def _profile_brief(profile: Dict[str, Any]) -> str:
    skills = ", ".join(str(s) for s in (profile.get("skills") or [])[:12]) or "not specified"
    lines = [
        f"- Current role: {profile.get('current_role') or 'n/a'}",
        f"- Domain: {profile.get('domain') or 'n/a'}",
        f"- Skills: {skills}",
    ]
    for exp in (profile.get("experiences") or [])[:3]:
        if isinstance(exp, dict):
            role = str(exp.get("role") or "").strip()
            company = str(exp.get("company") or "").strip()
            achievements = exp.get("achievements") or []
            first = str(achievements[0]).strip() if achievements else ""
            label = " at ".join(p for p in [role, company] if p) or "role"
            lines.append(f"- Experience: {label}{(' — ' + first) if first else ''}")
    return "\n".join(lines)


def generate_questions(
    target_role: str,
    seniority: str,
    domain: str,
    profile: Dict[str, Any],
    competency_labels: List[str],
) -> Dict[str, Any]:
    """Return {"opener": str|None, "questions": [...]} tailored to role + profile.

    `questions` is one per competency in order, or [] on failure (caller falls back
    to the question bank). `opener` is None on failure.
    """
    if not competency_labels:
        return {"opener": None, "questions": []}
    domain_part = f", domain: {domain}" if domain else ""
    comp_lines = "\n".join(f"{i + 1}. {label}" for i, label in enumerate(competency_labels))
    user_prompt = (
        f"Target role: {target_role} (seniority: {seniority}{domain_part}).\n"
        f"Candidate background:\n{_profile_brief(profile)}\n\n"
        f"Competencies to assess, in order:\n{comp_lines}\n\n"
        f"Return one opener plus exactly {len(competency_labels)} questions, one per competency, in order."
    )
    data = _groq_json(_QUESTIONS_SYSTEM, user_prompt, max_tokens=1000, temperature=0.5)
    result: Dict[str, Any] = {"opener": None, "questions": []}
    if isinstance(data, dict):
        opener = data.get("opener")
        if isinstance(opener, str) and opener.strip():
            result["opener"] = opener.strip()
        questions = data.get("questions")
        if (
            isinstance(questions, list)
            and len(questions) == len(competency_labels)
            and all(isinstance(q, str) and q.strip() for q in questions)
        ):
            result["questions"] = [q.strip() for q in questions]
    return result


# ── 2. In-session follow-up decision ─────────────────────────────────────────
_FOLLOWUP_SYSTEM = (
    "You are a professional interviewer deciding whether to ask one short "
    "follow-up probe. Maintain a neutral tone. Never praise, never give hints, "
    "never reveal you are an AI. Focus on what was missing or vague in the answer; "
    "you may reference the candidate's background only when it sharpens the probe "
    "(e.g. naming a specific tool or project they listed). Return ONLY JSON: "
    '{"should_follow_up": boolean, "probe": string}. should_follow_up is true '
    "only if the candidate's answer was surface-level, missing a concrete "
    "example, or missing the outcome. probe is one concise question (no preamble)."
)


def decide_follow_up(
    question: str, competency: str, answer: str, profile: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Decide whether to probe. Falls back to the question bank if Groq fails."""
    background = f"\nCandidate background:\n{_profile_brief(profile)}" if profile else ""
    data = _groq_json(
        _FOLLOWUP_SYSTEM,
        (
            f"Competency being assessed: {content.competency_label(competency)}\n"
            f"Question asked: {question}\n"
            f"Candidate answer: {answer[:2000]}"
            f"{background}"
        ),
        max_tokens=200,
        temperature=0.3,
    )
    if isinstance(data, dict) and isinstance(data.get("should_follow_up"), bool):
        probe = str(data.get("probe") or "").strip()
        if data["should_follow_up"] and probe:
            return {"should_follow_up": True, "probe": probe}
        if data["should_follow_up"]:
            return {"should_follow_up": True, "probe": content.fallback_probe(competency)}
        return {"should_follow_up": False, "probe": ""}
    # Groq unavailable: probe once for short answers, using the bank.
    if content.word_count(answer) < content.SHORT_ANSWER_WORDS:
        return {"should_follow_up": True, "probe": content.fallback_probe(competency)}
    return {"should_follow_up": False, "probe": ""}


# ── 3. Post-session feedback synthesis ───────────────────────────────────────
_FEEDBACK_SYSTEM = (
    "You are an expert interview coach reviewing a completed mock interview "
    "transcript. Give specific, behavioral, actionable feedback. Quote the "
    "candidate's actual words when identifying issues. Be honest, not "
    "encouraging. Return ONLY valid JSON (one object), no preamble, no markdown.\n"
    "Schema: {\n"
    '  "overall_summary": string (3-4 sentences max),\n'
    '  "headline_takeaway": string (single most important fix, one sentence),\n'
    '  "per_question_feedback": [{\n'
    '     "question": string, "competency": string,\n'
    '     "what_happened": string (brief, include a direct quote),\n'
    '     "what_worked": string, "what_was_missing": string,\n'
    '     "reconstructed_answer": string (their story reshaped stronger, keep their content)\n'
    "  }],\n"
    '  "recurring_patterns": [string],\n'
    '  "next_session_suggestion": string\n'
    "}"
)


def synthesize_feedback(
    profile: Dict[str, Any],
    competency_plan: Dict[str, Any],
    transcript: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    transcript_text = "\n".join(
        f"{t.get('speaker', '').upper()}: {t.get('content', '')}" for t in transcript
    )
    user_prompt = (
        f"Candidate target role context: {profile.get('current_role') or 'n/a'} "
        f"({profile.get('domain') or 'n/a'}).\n"
        f"Competency plan: {json.dumps(competency_plan)[:1500]}\n\n"
        f"Full transcript:\n{transcript_text[:12000]}"
    )
    data = _groq_json(_FEEDBACK_SYSTEM, user_prompt, max_tokens=4000, temperature=0.4)
    if isinstance(data, dict):
        data.setdefault("overall_summary", "")
        data.setdefault("headline_takeaway", "")
        data.setdefault("per_question_feedback", [])
        data.setdefault("recurring_patterns", [])
        data.setdefault("next_session_suggestion", "")
        if not isinstance(data["per_question_feedback"], list):
            data["per_question_feedback"] = []
        return data
    return None
