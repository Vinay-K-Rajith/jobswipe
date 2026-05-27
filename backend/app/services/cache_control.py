import logging

logger = logging.getLogger(__name__)


def clear_profile_dependent_caches() -> None:
    """Clear cached CSV/profile/model views after student or job data changes."""
    cleared = []

    try:
        from app.routers import swipe

        for fn_name in (
            "load_student_csv_rows",
            "load_student_feature_rows",
            "load_fairlearn_artifact",
        ):
            fn = getattr(swipe, fn_name, None)
            if fn and hasattr(fn, "cache_clear"):
                fn.cache_clear()
                cleared.append(f"swipe.{fn_name}")
            elif fn_name == "load_fairlearn_artifact" and hasattr(swipe, "clear_fairlearn_artifact_cache"):
                swipe.clear_fairlearn_artifact_cache()
                cleared.append("swipe.fairlearn_artifact")
    except Exception:
        logger.exception("Failed clearing swipe caches")

    try:
        from app.services import talentforge_matcher

        for fn_name in ("canonical_company_keys", "load_profiles"):
            fn = getattr(talentforge_matcher, fn_name, None)
            if fn and hasattr(fn, "cache_clear"):
                fn.cache_clear()
                cleared.append(f"talentforge_matcher.{fn_name}")
    except Exception:
        logger.exception("Failed clearing TalentForge caches")

    if cleared:
        logger.info("Cleared profile-dependent caches: %s", ", ".join(cleared))
