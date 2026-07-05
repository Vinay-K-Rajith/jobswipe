"""Skill string normalization for the live overlap scorers.

Pure functions only — no I/O, no model loading, no imports from the rest of the
app. Used by the serving-path overlap scorers (recommender.baseline_overlap_score
and talentforge_matcher._overlap_score) so that synonymous skills like "js" and
"javascript" count as the same skill instead of scoring zero overlap.
"""

from typing import Iterable, Set

# Intentionally minimal and extensible alias map: {alias -> canonical form}.
# Keys and values are lowercase. Add entries here as new synonyms surface; keep
# it small and hand-curated rather than pulling in a heavyweight taxonomy.
_ALIASES = {
    "js": "javascript",
    "py": "python",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "k8s": "kubernetes",
    "ts": "typescript",
    "ml": "machine learning",
    "dl": "deep learning",
}


def normalize_skill(s: str) -> str:
    """Lowercase, strip whitespace, then map through the alias table.

    Unknown skills pass through unchanged (just lowercased/stripped)."""
    if s is None:
        return ""
    key = str(s).strip().lower()
    return _ALIASES.get(key, key)


def normalize_skill_set(skills: Iterable[str]) -> Set[str]:
    """Normalize any iterable of skill strings into a set of canonical forms.

    Empty/blank entries are dropped. A bare string is treated as a single skill
    (not iterated character-by-character)."""
    if skills is None:
        return set()
    if isinstance(skills, str):
        skills = [skills]
    result: Set[str] = set()
    for s in skills:
        normalized = normalize_skill(s)
        if normalized:
            result.add(normalized)
    return result
