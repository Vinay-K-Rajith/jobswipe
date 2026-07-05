"""Static content + deterministic logic for the AI interview prep feature.

Everything here is rule-based (no LLM): role -> competency clusters, the
question bank, gap analysis from a structured profile, the question sequence
builder, and filler-word counting. Keeping this deterministic makes the core
interview flow reliable even when the LLM is unavailable.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

OPENER = "Walk me through your background and what brings you to this role."
CLOSER = "That's everything from my side. Do you have any questions for me?"

# Brief neutral acknowledgments rotated between scripted questions.
ACKS = ["Got it.", "Thank you.", "Understood.", "Okay.", "Thanks for that."]

# ── Role -> competency clusters ──────────────────────────────────────────────
ROLE_COMPETENCIES: Dict[str, List[str]] = {
    "software_engineer": [
        "technical_problem_solving", "system_thinking", "handling_ambiguity",
        "cross_functional_collaboration", "ownership_and_delivery",
        "stakeholder_communication", "conflict_resolution",
    ],
    "product_manager": [
        "prioritization_under_constraints", "cross_functional_influence",
        "data_driven_decisions", "user_empathy", "handling_failure",
        "stakeholder_management", "product_vision",
    ],
    "data_analyst": [
        "translating_ambiguity_to_questions", "data_quality_judgment",
        "presenting_to_non_technical_audiences", "stakeholder_communication",
        "handling_inconclusive_data", "technical_problem_solving",
    ],
    "marketing": [
        "campaign_thinking", "measuring_impact", "cross_functional_collaboration",
        "creative_under_constraint", "stakeholder_communication", "handling_failure",
    ],
}

# Fallback cluster for roles we don't have a hardcoded map for.
DEFAULT_COMPETENCIES = [
    "ownership_and_delivery", "handling_ambiguity", "cross_functional_collaboration",
    "stakeholder_communication", "conflict_resolution", "handling_failure",
]

# Synonyms -> canonical role key.
ROLE_ALIASES = {
    "swe": "software_engineer", "sde": "software_engineer",
    "software engineer": "software_engineer", "software developer": "software_engineer",
    "developer": "software_engineer", "backend engineer": "software_engineer",
    "frontend engineer": "software_engineer", "full stack": "software_engineer",
    "full stack engineer": "software_engineer", "programmer": "software_engineer",
    "pm": "product_manager", "product manager": "product_manager",
    "associate product manager": "product_manager", "apm": "product_manager",
    "data analyst": "data_analyst", "analyst": "data_analyst",
    "data scientist": "data_analyst", "business analyst": "data_analyst",
    "marketing": "marketing", "marketing manager": "marketing",
    "growth": "marketing", "digital marketing": "marketing",
}

# Human-readable competency labels (for UI + prompts).
COMPETENCY_LABELS = {
    "technical_problem_solving": "Technical problem solving",
    "system_thinking": "System thinking",
    "handling_ambiguity": "Handling ambiguity",
    "cross_functional_collaboration": "Cross-functional collaboration",
    "ownership_and_delivery": "Ownership & delivery",
    "stakeholder_communication": "Stakeholder communication",
    "conflict_resolution": "Conflict resolution",
    "prioritization_under_constraints": "Prioritization under constraints",
    "cross_functional_influence": "Cross-functional influence",
    "data_driven_decisions": "Data-driven decisions",
    "user_empathy": "User empathy",
    "handling_failure": "Handling failure",
    "stakeholder_management": "Stakeholder management",
    "product_vision": "Product vision",
    "translating_ambiguity_to_questions": "Translating ambiguity into questions",
    "data_quality_judgment": "Data quality judgment",
    "presenting_to_non_technical_audiences": "Presenting to non-technical audiences",
    "handling_inconclusive_data": "Handling inconclusive data",
    "campaign_thinking": "Campaign thinking",
    "measuring_impact": "Measuring impact",
    "creative_under_constraint": "Creativity under constraint",
}

# ── Question bank: competency -> core questions + follow-up probes ────────────
QUESTION_BANK: Dict[str, Dict[str, List[str]]] = {
    "technical_problem_solving": {
        "core": [
            "Tell me about the most technically challenging problem you've solved. How did you approach it?",
            "Describe a time you had to debug something difficult under pressure.",
        ],
        "probes": [
            "What specifically made that approach the right one over the alternatives?",
            "How did you verify your solution actually worked?",
        ],
    },
    "system_thinking": {
        "core": [
            "Walk me through a system or feature you designed end to end. What were the key trade-offs?",
            "Tell me about a time a design decision you made had consequences you didn't expect.",
        ],
        "probes": [
            "What would you change about that design if you built it again?",
            "How did you account for scale or failure in that design?",
        ],
    },
    "handling_ambiguity": {
        "core": [
            "Tell me about a time you had to make progress on a problem with unclear or missing requirements.",
            "Describe a project where the goal kept shifting. How did you handle it?",
        ],
        "probes": [
            "How did you decide what to do first when things were unclear?",
            "What did you do to reduce the ambiguity rather than just work around it?",
        ],
    },
    "cross_functional_collaboration": {
        "core": [
            "Tell me about a time you worked closely with people outside your own team to ship something.",
            "Describe a situation where another team's priorities clashed with yours.",
        ],
        "probes": [
            "What did you do specifically to get them aligned?",
            "How did you handle it when they didn't agree?",
        ],
    },
    "ownership_and_delivery": {
        "core": [
            "Tell me about something you owned end to end and shipped. What were you responsible for?",
            "Describe a time a project was at risk of slipping and what you did about it.",
        ],
        "probes": [
            "What was the outcome, and how did you measure it?",
            "What part of that was genuinely yours versus the team's?",
        ],
    },
    "stakeholder_communication": {
        "core": [
            "Tell me about a time you had to deliver difficult news to a stakeholder or manager.",
            "Describe a time you had to explain a complex topic to someone without your background.",
        ],
        "probes": [
            "How did they react, and how did you handle that?",
            "What would you do differently in how you communicated it?",
        ],
    },
    "conflict_resolution": {
        "core": [
            "Tell me about a time your approach conflicted with your team's direction, and you still had to deliver together.",
            "Describe a situation where you disagreed with a decision made by someone senior to you. What did you do?",
        ],
        "probes": [
            "What was your reasoning behind that decision specifically?",
            "Looking back, what would you do differently?",
        ],
    },
    "prioritization_under_constraints": {
        "core": [
            "Tell me about a time you had far more to do than was possible. How did you decide what mattered?",
            "Describe a hard trade-off you made between scope, time, and quality.",
        ],
        "probes": [
            "What did you explicitly choose NOT to do, and why?",
            "How did you communicate that prioritization to others?",
        ],
    },
    "cross_functional_influence": {
        "core": [
            "Tell me about a time you got a team to do something without having authority over them.",
            "Describe a time you changed someone's mind on an important decision.",
        ],
        "probes": [
            "What specifically convinced them?",
            "What would you have done if they still said no?",
        ],
    },
    "data_driven_decisions": {
        "core": [
            "Tell me about a decision you made primarily based on data. What did the data say?",
            "Describe a time the data contradicted your intuition. What did you do?",
        ],
        "probes": [
            "How confident were you in that data, and why?",
            "What was the outcome of that decision?",
        ],
    },
    "user_empathy": {
        "core": [
            "Tell me about a time you deeply understood a user's problem and it changed what you built.",
            "Describe a time you advocated for the user against business or technical pressure.",
        ],
        "probes": [
            "How did you actually learn what the user needed?",
            "What was the impact of that change?",
        ],
    },
    "handling_failure": {
        "core": [
            "Tell me about a time something you owned failed. What happened?",
            "Describe your biggest professional mistake and what you learned.",
        ],
        "probes": [
            "What specifically would you do differently now?",
            "What did you change in how you work as a result?",
        ],
    },
    "stakeholder_management": {
        "core": [
            "Tell me about a time you managed conflicting expectations from multiple stakeholders.",
            "Describe a time you had to say no to an important stakeholder.",
        ],
        "probes": [
            "How did you keep them aligned over time?",
            "How did they respond, and how did you handle it?",
        ],
    },
    "product_vision": {
        "core": [
            "Tell me about a product or feature direction you set. How did you decide on it?",
            "Describe how you'd think about where a product should go in the next year.",
        ],
        "probes": [
            "What evidence did you use to back that direction?",
            "How did you get others bought into it?",
        ],
    },
    "translating_ambiguity_to_questions": {
        "core": [
            "Tell me about a vague request you received and how you turned it into something analyzable.",
            "Describe a time a stakeholder asked for 'insights' with no clear question. What did you do?",
        ],
        "probes": [
            "What questions did you ask to narrow it down?",
            "How did you confirm you were solving the right problem?",
        ],
    },
    "data_quality_judgment": {
        "core": [
            "Tell me about a time you found a problem with the data you were given.",
            "Describe how you decide whether a dataset is trustworthy enough to act on.",
        ],
        "probes": [
            "What did you do once you spotted the issue?",
            "How did you communicate the limitation to stakeholders?",
        ],
    },
    "presenting_to_non_technical_audiences": {
        "core": [
            "Tell me about a time you presented analysis to a non-technical audience.",
            "Describe how you make a complex finding land with executives.",
        ],
        "probes": [
            "How did you decide what to leave out?",
            "How did you know they actually understood it?",
        ],
    },
    "handling_inconclusive_data": {
        "core": [
            "Tell me about a time your analysis didn't give a clear answer. What did you do?",
            "Describe a situation where you had to make a recommendation with incomplete data.",
        ],
        "probes": [
            "How did you communicate the uncertainty?",
            "What was the outcome of that recommendation?",
        ],
    },
    "campaign_thinking": {
        "core": [
            "Tell me about a campaign you planned end to end. How did you approach it?",
            "Describe a campaign that underperformed and what you learned.",
        ],
        "probes": [
            "How did you decide on the channel and message?",
            "What would you change about it now?",
        ],
    },
    "measuring_impact": {
        "core": [
            "Tell me about a time you proved the impact of your work with numbers.",
            "Describe how you decide what metric actually matters for an initiative.",
        ],
        "probes": [
            "How did you attribute the result to your work specifically?",
            "What did you do when the metric didn't move?",
        ],
    },
    "creative_under_constraint": {
        "core": [
            "Tell me about a time you did something creative with very limited resources.",
            "Describe a constraint that actually led to a better outcome.",
        ],
        "probes": [
            "What made that solution work?",
            "How did you get others on board with the idea?",
        ],
    },
}

GENERIC_PROBES = [
    "Can you give me a specific example of that?",
    "What was your exact role in that, versus the team's?",
    "What was the measurable outcome?",
]

FILLER_PATTERNS = [
    r"\bum\b", r"\buh\b", r"\berm\b", r"\blike\b", r"\byou know\b",
    r"\bbasically\b", r"\bsort of\b", r"\bkind of\b", r"\bi mean\b",
    r"\bactually\b", r"\bliterally\b",
]

# Heuristic: answers shorter than this (in words) may warrant a follow-up probe.
SHORT_ANSWER_WORDS = 70


def normalize_role(role: str) -> str:
    key = re.sub(r"[^a-z0-9 ]", "", str(role or "").strip().lower())
    if key in ROLE_ALIASES:
        return ROLE_ALIASES[key]
    if key in ROLE_COMPETENCIES:
        return key
    # token containment fallback (e.g. "senior software engineer ii")
    for alias, canonical in ROLE_ALIASES.items():
        if alias in key:
            return canonical
    return "__default__"


def competencies_for_role(role: str) -> List[str]:
    return ROLE_COMPETENCIES.get(normalize_role(role), DEFAULT_COMPETENCIES)


def competency_label(key: str) -> str:
    return COMPETENCY_LABELS.get(key, key.replace("_", " ").capitalize())


def _profile_evidence_tokens(profile: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.extend(str(s) for s in (profile.get("skills") or []))
    for exp in (profile.get("experiences") or []):
        if isinstance(exp, dict):
            parts.append(str(exp.get("role") or ""))
            parts.append(str(exp.get("company") or ""))
            parts.extend(str(a) for a in (exp.get("achievements") or []))
        else:
            parts.append(str(exp))
    parts.append(str(profile.get("current_role") or ""))
    parts.append(str(profile.get("domain") or ""))
    blob = " ".join(parts).lower()
    return re.findall(r"[a-z]+", blob)


# Keyword hints used to detect resume evidence per competency.
_COMPETENCY_KEYWORDS: Dict[str, List[str]] = {
    "technical_problem_solving": ["debug", "optimi", "algorithm", "performance", "bug", "build", "engineer", "code", "solve"],
    "system_thinking": ["design", "architect", "scal", "system", "infrastructure", "pipeline", "distributed"],
    "handling_ambiguity": ["ambig", "research", "explor", "prototype", "zero to one", "greenfield", "unclear"],
    "cross_functional_collaboration": ["collaborat", "cross", "team", "partner", "stakeholder", "coordinat"],
    "ownership_and_delivery": ["own", "led", "lead", "shipped", "deliver", "launch", "drove", "responsible"],
    "stakeholder_communication": ["present", "communicat", "stakeholder", "report", "document", "explain"],
    "conflict_resolution": ["conflict", "negotiat", "align", "disagree", "mediat"],
    "prioritization_under_constraints": ["prioriti", "roadmap", "backlog", "trade", "deadline", "scope"],
    "cross_functional_influence": ["influence", "convince", "stakeholder", "align", "partner", "cross"],
    "data_driven_decisions": ["data", "metric", "analytics", "ab test", "experiment", "sql", "measur"],
    "user_empathy": ["user", "customer", "research", "interview", "usability", "persona"],
    "handling_failure": ["failure", "mistake", "learn", "postmortem", "retro", "incident"],
    "stakeholder_management": ["stakeholder", "manage", "expectation", "executive", "client"],
    "product_vision": ["vision", "strategy", "roadmap", "product", "direction"],
    "translating_ambiguity_to_questions": ["requirement", "scope", "question", "stakeholder", "ambig"],
    "data_quality_judgment": ["data", "quality", "clean", "validat", "etl", "pipeline"],
    "presenting_to_non_technical_audiences": ["present", "dashboard", "report", "visual", "stakeholder", "executive"],
    "handling_inconclusive_data": ["data", "analysis", "uncertain", "recommend", "insight"],
    "campaign_thinking": ["campaign", "marketing", "channel", "brand", "content", "launch"],
    "measuring_impact": ["metric", "roi", "impact", "conversion", "growth", "kpi", "measur"],
    "creative_under_constraint": ["creative", "design", "budget", "constraint", "scrappy", "resourceful"],
}


def analyze_gaps(profile: Dict[str, Any], competencies: List[str]) -> Dict[str, List[str]]:
    """Classify each competency as strength / risk / blind_spot from resume evidence."""
    tokens = set(_profile_evidence_tokens(profile))
    strengths, risks, blind_spots = [], [], []
    for comp in competencies:
        keywords = _COMPETENCY_KEYWORDS.get(comp, [])
        score = sum(1 for kw in keywords if any(kw in tok or tok.startswith(kw) for tok in tokens))
        if score >= 2:
            strengths.append(comp)
        elif score == 1:
            risks.append(comp)
        else:
            blind_spots.append(comp)
    return {"strengths": strengths, "risks": risks, "blind_spots": blind_spots}


def build_question_sequence(gaps: Dict[str, List[str]], max_questions: int = 7) -> List[Dict[str, str]]:
    """Opener -> strengths -> risks -> a blind spot -> closer.

    Each entry: {competency, question, type}. type in {opener, core, closer}.
    """
    sequence: List[Dict[str, str]] = [
        {"competency": "intro", "question": OPENER, "type": "opener"}
    ]

    def pick(comp: str) -> str:
        bank = QUESTION_BANK.get(comp)
        if bank and bank.get("core"):
            return bank["core"][0]
        return f"Tell me about a time you demonstrated {competency_label(comp).lower()}."

    ordered: List[str] = []
    ordered += gaps.get("strengths", [])[:2]
    ordered += gaps.get("risks", [])[:3]
    ordered += gaps.get("blind_spots", [])[:1]

    # Backfill from any remaining competency if buckets were sparse.
    if len(ordered) < max_questions - 2:
        leftovers = [
            c for c in (gaps.get("strengths", []) + gaps.get("risks", []) + gaps.get("blind_spots", []))
            if c not in ordered
        ]
        ordered += leftovers

    seen = set()
    body_budget = max_questions - 2  # reserve opener + closer
    for comp in ordered:
        if comp in seen:
            continue
        seen.add(comp)
        sequence.append({"competency": comp, "question": pick(comp), "type": "core"})
        if len(sequence) - 1 >= body_budget:
            break

    sequence.append({"competency": "closing", "question": CLOSER, "type": "closer"})
    return sequence


def fallback_probe(competency: str) -> str:
    bank = QUESTION_BANK.get(competency)
    if bank and bank.get("probes"):
        return bank["probes"][0]
    return GENERIC_PROBES[0]


def count_filler_words(text: str) -> int:
    lowered = (text or "").lower()
    return sum(len(re.findall(pattern, lowered)) for pattern in FILLER_PATTERNS)


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def ack_for_index(index: int) -> str:
    return ACKS[index % len(ACKS)]
