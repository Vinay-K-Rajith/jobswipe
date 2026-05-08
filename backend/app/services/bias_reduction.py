import json
import os
import pickle
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from scipy.stats import fisher_exact, spearmanr
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.model.inference import build_inference_features

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
LOCAL_RECOMMENDATIONS_PATH = os.path.join(MODEL_DIR, "bias_recommendations_local.json")
LOCAL_FAIRNESS_HISTORY_PATH = os.path.join(MODEL_DIR, "model_fairness_history_local.json")

load_dotenv(ENV_PATH)

PROJECT_COMPLEXITY_LEVELS = {
    "None": 0,
    "Basic": 1,
    "Intermediate": 2,
    "Advanced": 3,
}
PROJECT_COMPLEXITY_LABELS = {value: key for key, value in PROJECT_COMPLEXITY_LEVELS.items()}

CRITERION_ALIASES = {
    "cgpa": "cgpa",
    "tenth": "10th",
    "10th": "10th",
    "twelfth": "12th",
    "12th": "12th",
    "backlog": "backlog",
    "backlogs": "backlog",
    "department": "department",
    "dept": "department",
}

SOFT_THRESHOLD = 0.35
FAIRNESS_ARTIFACTS = {
    "baseline": {
        "model": "model.pkl",
        "scaler": "scaler.pkl",
        "features": "feature_columns.json",
        "label": "Baseline XGBoost",
        "kind": "classic",
    },
    "champion": {
        "bundle": "fairlearn_lightgbm_eps_0.01.pkl",
        "label": "Fairlearn LightGBM ε=0.01",
        "kind": "bundle",
    },
    "tightened": {
        "bundle": "fairlearn_lightgbm_eps_0.005.pkl",
        "label": "Fairlearn LightGBM ε=0.005",
        "kind": "bundle",
    },
}


@dataclass
class PersistenceStatus:
    available: bool
    reason: Optional[str] = None
    client: Any = None


def ensure_parent_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def read_local_records(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_local_records(path: str, records: List[Dict[str, Any]]) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(clean_nan(records), handle, indent=2)


def clean_nan(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    if isinstance(obj, float) and np.isnan(obj):
        return None
    if isinstance(obj, np.floating):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def get_persistence_client() -> PersistenceStatus:
    try:
        from supabase import create_client  # type: ignore
    except Exception:
        return PersistenceStatus(False, "Supabase Python package is not installed.")

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return PersistenceStatus(False, "Supabase environment variables are not configured.")

    try:
        client = create_client(url, key)
    except Exception as exc:
        return PersistenceStatus(False, f"Failed to initialize Supabase client: {exc}")

    return PersistenceStatus(True, client=client)


def build_bias_frame(students_df: pd.DataFrame, student_features_df: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [
        "student_id",
        "total_internship_months",
        "num_verified_skills",
        "max_project_complexity",
        "num_projects",
        "skill_list",
        "cgpa_normalized",
        "10th_normalized",
        "12th_normalized",
        "max_internship_tier",
        "num_global_premium",
        "num_global_standard",
        "num_national",
        "max_cert_tier",
        "num_papers",
        "max_paper_tier",
        "num_advanced_skills",
    ]
    frame = students_df.merge(
        student_features_df[[col for col in feature_cols if col in student_features_df.columns]],
        on="student_id",
        how="left",
        suffixes=("", "_feat"),
    )
    frame["total_internship_months"] = frame["total_internship_months"].fillna(0.0)
    frame["num_verified_skills"] = frame["num_verified_skills"].fillna(0).astype(int)
    frame["max_project_complexity"] = frame["max_project_complexity"].fillna(0).astype(int)
    frame["num_projects"] = frame["num_projects"].fillna(0).astype(int)
    frame["skill_list"] = frame["skill_list"].apply(lambda value: value if isinstance(value, list) else [])
    return frame


def get_company_record(companies_df: pd.DataFrame, company_id: str) -> Dict[str, Any]:
    company = companies_df[companies_df["company_id"] == company_id]
    if company.empty:
        raise ValueError(f"Company {company_id} not found")
    return company.iloc[0].to_dict()


def normalize_criterion_name(criterion: str) -> str:
    normalized = CRITERION_ALIASES.get(str(criterion).strip().lower())
    if not normalized:
        raise ValueError(f"Unsupported criterion '{criterion}'")
    return normalized


def allowed_departments(company: Dict[str, Any]) -> List[str]:
    return [dept.strip() for dept in str(company.get("allowed_departments", "")).split(",") if dept.strip()]


def apply_rule_mask(
    frame: pd.DataFrame,
    company: Dict[str, Any],
    ignored_criteria: Optional[Iterable[str]] = None,
    substitution: Optional[Dict[str, Any]] = None,
) -> pd.Series:
    ignored = set(ignored_criteria or [])
    mask = pd.Series(True, index=frame.index)

    if "cgpa" not in ignored:
        mask &= frame["cgpa"] >= float(company.get("min_cgpa", 0) or 0)
    if "10th" not in ignored:
        mask &= frame["10th_marks"] >= float(company.get("min_10th", 0) or 0)
    if "12th" not in ignored:
        mask &= frame["12th_marks"] >= float(company.get("min_12th", 0) or 0)
    if "backlog" not in ignored:
        mask &= frame["active_backlogs"] <= int(company.get("max_active_backlogs", 0) or 0)
    if "department" not in ignored:
        mask &= frame["department"].isin(allowed_departments(company))

    if substitution:
        mask &= substitution_mask(frame, substitution)

    return mask.fillna(False)


def substitution_mask(frame: pd.DataFrame, substitution: Dict[str, Any]) -> pd.Series:
    kind = substitution["kind"]
    value = substitution["value"]

    if kind == "cgpa":
        return frame["cgpa"] >= float(value)
    if kind == "verified_skills":
        return frame["num_verified_skills"] >= int(value)
    if kind == "internship_months":
        return frame["total_internship_months"] >= float(value)
    if kind == "project_complexity":
        return frame["max_project_complexity"] >= int(value)

    raise ValueError(f"Unsupported substitution kind '{kind}'")


def compute_gender_metrics(pass_mask: pd.Series, gender_series: pd.Series) -> Dict[str, Any]:
    audit_df = pd.DataFrame({
        "passed": pass_mask.astype(int),
        "gender": gender_series.fillna("Unknown"),
    })
    rates = audit_df.groupby("gender")["passed"].mean().to_dict()
    counts = {
        gender: {
            "pass": int(group["passed"].sum()),
            "fail": int((1 - group["passed"]).sum()),
            "total": int(len(group)),
        }
        for gender, group in audit_df.groupby("gender")
    }

    disparity = max(rates.values()) - min(rates.values()) if rates else 0.0
    female = counts.get("F", {"pass": 0, "fail": 0})
    male = counts.get("M", {"pass": 0, "fail": 0})

    table = [[female["pass"], female["fail"]], [male["pass"], male["fail"]]]
    p_value = 1.0
    if sum(table[0]) > 0 and sum(table[1]) > 0:
        _, p_value = fisher_exact(table)

    return {
        "pass_rates": {key: round(float(value), 4) for key, value in rates.items()},
        "counts": counts,
        "disparity": round(float(disparity), 4),
        "p_value": round(float(p_value), 6),
    }


def build_level1_candidate_result(
    threshold_value: float,
    pass_mask: pd.Series,
    gender_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    counts = gender_metrics["counts"]
    return {
        "threshold": threshold_value,
        "total_eligible": int(pass_mask.sum()),
        "female_eligible": int(counts.get("F", {}).get("pass", 0)),
        "male_eligible": int(counts.get("M", {}).get("pass", 0)),
        "non_binary_eligible": int(counts.get("Non-binary", {}).get("pass", 0)),
        "gender_disparity": gender_metrics["disparity"],
        "p_value": gender_metrics["p_value"],
        "pass_rates": gender_metrics["pass_rates"],
    }


def threshold_candidates(current_value: float, criterion: str) -> List[float]:
    if criterion == "backlog":
        values = {0, 1, 2, 3, int(current_value)}
        return sorted(values)
    if criterion == "cgpa":
        floor = max(0.0, current_value - 1.5)
        values = [round(max(floor, current_value - (0.15 * step)), 2) for step in range(10)]
        return sorted(set(values))

    floor = max(0.0, current_value - 15.0)
    values = [round(max(floor, current_value - (1.5 * step)), 1) for step in range(10)]
    return sorted(set(values))


def set_company_threshold(company: Dict[str, Any], criterion: str, value: float) -> Dict[str, Any]:
    updated = dict(company)
    if criterion == "cgpa":
        updated["min_cgpa"] = float(value)
    elif criterion == "10th":
        updated["min_10th"] = float(value)
    elif criterion == "12th":
        updated["min_12th"] = float(value)
    elif criterion == "backlog":
        updated["max_active_backlogs"] = int(value)
    else:
        raise ValueError(f"Criterion '{criterion}' cannot be swept")
    return updated


def criterion_current_value(company: Dict[str, Any], criterion: str) -> float:
    if criterion == "cgpa":
        return float(company.get("min_cgpa", 0) or 0)
    if criterion == "10th":
        return float(company.get("min_10th", 0) or 0)
    if criterion == "12th":
        return float(company.get("min_12th", 0) or 0)
    if criterion == "backlog":
        return float(company.get("max_active_backlogs", 0) or 0)
    raise ValueError(f"Criterion '{criterion}' cannot be swept")


def simulate_fix(
    company_id: str,
    criterion: str,
    students_df: pd.DataFrame,
    companies_df: pd.DataFrame,
    student_features_df: pd.DataFrame,
) -> Dict[str, Any]:
    normalized = normalize_criterion_name(criterion)
    if normalized not in {"cgpa", "10th", "12th", "backlog"}:
        raise ValueError("Criterion sensitivity supports cgpa, tenth, twelfth, or backlog only")

    company = get_company_record(companies_df, company_id)
    frame = build_bias_frame(students_df, student_features_df)

    current_value = criterion_current_value(company, normalized)
    baseline_mask = apply_rule_mask(frame, company)
    baseline_gender = compute_gender_metrics(baseline_mask, frame["gender"])
    baseline_pool = int(baseline_mask.sum())

    sweep_results = []
    for value in threshold_candidates(current_value, normalized):
        simulated_company = set_company_threshold(company, normalized, value)
        pass_mask = apply_rule_mask(frame, simulated_company)
        gender_metrics = compute_gender_metrics(pass_mask, frame["gender"])
        sweep_results.append(build_level1_candidate_result(value, pass_mask, gender_metrics))

    sweep_results.sort(key=lambda item: item["threshold"])
    recommended = next(
        (
            item for item in sweep_results
            if item["gender_disparity"] < 0.05 and item["total_eligible"] >= int(np.ceil(baseline_pool * 0.8))
        ),
        None,
    )

    return clean_nan({
        "company_id": company_id,
        "company_name": company.get("company_name", ""),
        "criterion": normalized,
        "current_threshold": current_value,
        "current_disparity": baseline_gender["disparity"],
        "current_pool_size": baseline_pool,
        "sweep": sweep_results,
        "recommended_threshold": None if not recommended else recommended["threshold"],
        "recommended_result": recommended,
    })


def leave_one_out_drivers(frame: pd.DataFrame, company: Dict[str, Any]) -> List[Dict[str, Any]]:
    baseline_mask = apply_rule_mask(frame, company)
    baseline_metrics = compute_gender_metrics(baseline_mask, frame["gender"])
    baseline_disparity = baseline_metrics["disparity"]

    drivers = []
    for criterion in ["cgpa", "10th", "12th", "backlog", "department"]:
        variant_mask = apply_rule_mask(frame, company, ignored_criteria=[criterion])
        metrics = compute_gender_metrics(variant_mask, frame["gender"])
        drivers.append({
            "criterion": criterion,
            "baseline_disparity": baseline_disparity,
            "disparity_without_criterion": metrics["disparity"],
            "disparity_reduction": round(float(baseline_disparity - metrics["disparity"]), 4),
            "pool_size_without_criterion": int(variant_mask.sum()),
        })

    return sorted(drivers, key=lambda item: item["disparity_reduction"], reverse=True)


def candidate_search_space(kind: str, frame: pd.DataFrame) -> List[Any]:
    if kind == "cgpa":
        return sorted({round(float(value), 2) for value in frame["cgpa"].dropna().tolist()})
    if kind == "verified_skills":
        return sorted({int(value) for value in frame["num_verified_skills"].dropna().tolist()})
    if kind == "internship_months":
        return sorted({round(float(value), 1) for value in frame["total_internship_months"].dropna().tolist()})
    if kind == "project_complexity":
        return [1, 2, 3]
    raise ValueError(f"Unsupported candidate space '{kind}'")


def substitution_label(kind: str, value: Any) -> str:
    if kind == "cgpa":
        return f"CGPA at least {value:.2f}"
    if kind == "verified_skills":
        return f"Verified skills at least {int(value)}"
    if kind == "internship_months":
        return f"Internship duration at least {float(value):.1f} months"
    if kind == "project_complexity":
        return f"Project complexity at least {PROJECT_COMPLEXITY_LABELS.get(int(value), 'Basic')}"
    return str(value)


def candidate_plain_english(driver: str, substitution: Dict[str, Any]) -> str:
    driver_label = {
        "10th": "10th-grade cutoff",
        "12th": "12th-grade cutoff",
        "cgpa": "CGPA cutoff",
        "backlog": "backlog cap",
        "department": "department filter",
    }.get(driver, driver)
    return f"Replace the {driver_label} with {substitution_label(substitution['kind'], substitution['value'])}."


def performance_preservation(original_mask: pd.Series, candidate_mask: pd.Series) -> float:
    if original_mask.equals(candidate_mask):
        return 1.0
    correlation = spearmanr(original_mask.astype(int), candidate_mask.astype(int)).correlation
    if correlation is None or np.isnan(correlation):
        return 0.0
    return float(max(min(correlation, 1.0), -1.0))


def substitution_candidates_for_driver(
    frame: pd.DataFrame,
    company: Dict[str, Any],
    driver: str,
    original_mask: pd.Series,
) -> List[Dict[str, Any]]:
    original_pool = int(original_mask.sum())
    candidate_kinds: List[str]
    if driver in {"10th", "12th"}:
        candidate_kinds = ["cgpa", "verified_skills", "internship_months"]
    elif driver == "cgpa":
        candidate_kinds = ["verified_skills", "project_complexity"]
    else:
        candidate_kinds = ["cgpa", "verified_skills", "internship_months"]

    generated: List[Dict[str, Any]] = []
    for kind in candidate_kinds:
        best_result: Optional[Dict[str, Any]] = None
        for value in candidate_search_space(kind, frame):
            substitution = {"kind": kind, "value": value}
            candidate_mask = apply_rule_mask(frame, company, ignored_criteria=[driver], substitution=substitution)
            candidate_pool = int(candidate_mask.sum())
            pool_distance = abs(candidate_pool - original_pool)
            gender_metrics = compute_gender_metrics(candidate_mask, frame["gender"])
            candidate = {
                "kind": kind,
                "value": value,
                "mask": candidate_mask,
                "pool_size": candidate_pool,
                "pool_distance": pool_distance,
                "gender_disparity": gender_metrics["disparity"],
                "p_value": gender_metrics["p_value"],
                "pass_rates": gender_metrics["pass_rates"],
                "performance_preservation_score": round(performance_preservation(original_mask, candidate_mask), 4),
            }
            if (
                best_result is None
                or candidate["pool_distance"] < best_result["pool_distance"]
                or (
                    candidate["pool_distance"] == best_result["pool_distance"]
                    and candidate["gender_disparity"] < best_result["gender_disparity"]
                )
            ):
                best_result = candidate

        if best_result is not None:
            generated.append(best_result)

    for candidate in generated:
        pool_similarity = max(0.0, 1 - (abs(candidate["pool_size"] - original_pool) / max(original_pool, 1)))
        candidate["pool_similarity"] = round(pool_similarity, 4)

    if generated:
        disparities = [item["gender_disparity"] for item in generated]
        min_disp, max_disp = min(disparities), max(disparities)
        for candidate in generated:
            if max_disp == min_disp:
                normalized_disparity = 0.0
            else:
                normalized_disparity = (candidate["gender_disparity"] - min_disp) / (max_disp - min_disp)
            composite = (
                0.5 * (1 - normalized_disparity) +
                0.3 * candidate["performance_preservation_score"] +
                0.2 * candidate["pool_similarity"]
            )
            confidence = "high" if candidate["performance_preservation_score"] > 0.85 else "medium" if candidate["performance_preservation_score"] > 0.70 else "low"
            candidate["composite_score"] = round(composite, 4)
            candidate["confidence"] = confidence

    generated.sort(key=lambda item: item["composite_score"], reverse=True)
    return generated


def counterfactual_rules(
    company_id: str,
    students_df: pd.DataFrame,
    companies_df: pd.DataFrame,
    student_features_df: pd.DataFrame,
) -> Dict[str, Any]:
    company = get_company_record(companies_df, company_id)
    frame = build_bias_frame(students_df, student_features_df)
    original_mask = apply_rule_mask(frame, company)
    original_metrics = compute_gender_metrics(original_mask, frame["gender"])
    drivers = leave_one_out_drivers(frame, company)
    top_driver = drivers[0]["criterion"] if drivers else "cgpa"

    candidates = substitution_candidates_for_driver(frame, company, top_driver, original_mask)[:3]
    payload = []
    for index, candidate in enumerate(candidates, start=1):
        payload.append({
            "candidate_id": f"{company_id}-{top_driver}-{candidate['kind']}-{index}",
            "description": candidate_plain_english(top_driver, candidate),
            "confidence": candidate["confidence"],
            "composite_score": candidate["composite_score"],
            "current_rule": {
                "criterion": top_driver,
                "threshold": criterion_current_value(company, top_driver) if top_driver != "department" else company.get("allowed_departments", ""),
                "gender_disparity": original_metrics["disparity"],
                "pool_size": int(original_mask.sum()),
            },
            "alternative_rule": {
                "criterion": candidate["kind"],
                "threshold": candidate["value"],
                "label": substitution_label(candidate["kind"], candidate["value"]),
                "gender_disparity": candidate["gender_disparity"],
                "pool_size": candidate["pool_size"],
                "p_value": candidate["p_value"],
                "performance_preservation_score": candidate["performance_preservation_score"],
                "pool_similarity": candidate["pool_similarity"],
            },
            "spec": {
                "remove_criterion": top_driver,
                "substitution": {
                    "kind": candidate["kind"],
                    "value": candidate["value"],
                },
            },
        })

    return clean_nan({
        "company_id": company_id,
        "company_name": company.get("company_name", ""),
        "drivers": drivers[:3],
        "top_driver": top_driver,
        "current_metrics": {
            "pool_size": int(original_mask.sum()),
            "gender_disparity": original_metrics["disparity"],
            "p_value": original_metrics["p_value"],
        },
        "candidates": payload,
    })


def preview_substitution(
    company_id: str,
    spec: Dict[str, Any],
    students_df: pd.DataFrame,
    companies_df: pd.DataFrame,
    student_features_df: pd.DataFrame,
) -> Dict[str, Any]:
    company = get_company_record(companies_df, company_id)
    frame = build_bias_frame(students_df, student_features_df)
    remove_criterion = normalize_criterion_name(spec["remove_criterion"])
    substitution = spec["substitution"]
    original_mask = apply_rule_mask(frame, company)
    candidate_mask = apply_rule_mask(frame, company, ignored_criteria=[remove_criterion], substitution=substitution)

    newly_eligible = frame[(~original_mask) & candidate_mask]
    group_rows = (
        newly_eligible.groupby(["department", "gender"]).size().reset_index(name="count")
        if not newly_eligible.empty
        else pd.DataFrame(columns=["department", "gender", "count"])
    )

    return clean_nan({
        "company_id": company_id,
        "newly_eligible_count": int(len(newly_eligible)),
        "dropped_count": int((original_mask & ~candidate_mask).sum()),
        "grouped": group_rows.to_dict(orient="records"),
        "students": newly_eligible[["student_id", "full_name", "department", "gender", "cgpa"]].to_dict(orient="records"),
    })


def save_bias_recommendation(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = {
        "id": int(time.time() * 1000),
        "company_id": payload["company_id"],
        "criterion": payload["criterion"],
        "current_threshold": payload.get("current_threshold"),
        "recommended_threshold": payload.get("recommended_threshold"),
        "current_disparity": payload.get("current_disparity"),
        "projected_disparity": payload.get("projected_disparity"),
        "current_pool_size": payload.get("current_pool_size"),
        "projected_pool_size": payload.get("projected_pool_size"),
        "status": payload.get("status", "proposed"),
        "recommendation_type": payload.get("recommendation_type", "threshold"),
        "simulation_payload": payload.get("simulation_payload"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    persistence = get_persistence_client()
    if persistence.available and persistence.client is not None:
        try:
            response = persistence.client.table("bias_recommendations").insert(record).execute()
            saved = response.data[0] if response.data else record
            saved["persistence_mode"] = "supabase"
            return clean_nan(saved)
        except Exception:
            pass

    records = read_local_records(LOCAL_RECOMMENDATIONS_PATH)
    record["persistence_mode"] = "local"
    records.append(record)
    write_local_records(LOCAL_RECOMMENDATIONS_PATH, records)
    return clean_nan(record)


def load_training_labels() -> pd.DataFrame:
    return pd.read_csv(os.path.join(DATA_DIR, "training_labels.csv"))


def build_company_feature_matrix(
    company_id: str,
    students_df: pd.DataFrame,
    companies_df: pd.DataFrame,
    student_features_df: pd.DataFrame,
) -> pd.DataFrame:
    company = get_company_record(companies_df, company_id)
    rows = []
    for _, student in student_features_df.iterrows():
        raw = students_df[students_df["student_id"] == student["student_id"]].iloc[0].to_dict()
        student_data = student.to_dict()
        student_data.update(raw)
        pair_features = build_inference_features(student_data, company)
        pair_features["student_id"] = student["student_id"]
        rows.append(pair_features)
    return pd.DataFrame(rows)


def demographic_parity_gap(y_pred: np.ndarray, genders: pd.Series) -> float:
    rates = pd.DataFrame({"pred": y_pred, "gender": genders}).groupby("gender")["pred"].mean()
    if rates.empty:
        return 0.0
    return float(rates.max() - rates.min())


def equalized_odds_gap(y_true: np.ndarray, y_pred: np.ndarray, genders: pd.Series) -> float:
    per_group = []
    frame = pd.DataFrame({"actual": y_true, "pred": y_pred, "gender": genders})
    for _, group in frame.groupby("gender"):
        positives = group[group["actual"] == 1]
        negatives = group[group["actual"] == 0]
        tpr = positives["pred"].mean() if not positives.empty else 0.0
        fpr = negatives["pred"].mean() if not negatives.empty else 0.0
        per_group.append((float(tpr), float(fpr)))
    if not per_group:
        return 0.0
    tpr_gap = max(item[0] for item in per_group) - min(item[0] for item in per_group)
    fpr_gap = max(item[1] for item in per_group) - min(item[1] for item in per_group)
    return float(max(tpr_gap, fpr_gap))


def shortlist_overlap(shortlist_a: List[str], shortlist_b: List[str]) -> float:
    set_a = set(shortlist_a)
    set_b = set(shortlist_b)
    if not set_a and not set_b:
        return 1.0
    return float(len(set_a & set_b) / max(len(set_a | set_b), 1))


def load_variant_artifact(key: str) -> Dict[str, Any]:
    config = FAIRNESS_ARTIFACTS[key]
    if config["kind"] == "classic":
        model_path = os.path.join(MODEL_DIR, config["model"])
        scaler_path = os.path.join(MODEL_DIR, config["scaler"])
        feature_path = os.path.join(MODEL_DIR, config["features"])
        if not (os.path.exists(model_path) and os.path.exists(scaler_path) and os.path.exists(feature_path)):
            raise FileNotFoundError(f"Missing baseline artifact(s) for {key}")
        with open(model_path, "rb") as model_file:
            model = pickle.load(model_file)
        with open(scaler_path, "rb") as scaler_file:
            scaler = pickle.load(scaler_file)
        with open(feature_path, "r", encoding="utf-8") as feature_file:
            feature_cols = json.load(feature_file)
        return {"model": model, "scaler": scaler, "feature_cols": feature_cols, "label": config["label"]}

    bundle_path = os.path.join(MODEL_DIR, config["bundle"])
    if not os.path.exists(bundle_path):
        raise FileNotFoundError(f"Missing fairness artifact '{config['bundle']}'")
    with open(bundle_path, "rb") as bundle_file:
        bundle = pickle.load(bundle_file)
    bundle["label"] = config["label"]
    return bundle


def ranker_shortlist_for_company(
    company_id: str,
    students_df: pd.DataFrame,
    student_features_df: pd.DataFrame,
    companies_df: pd.DataFrame,
    ranker: Any,
    ranker_scaler: Any,
    ranker_feat_cols: List[str],
    top_k: int = 20,
) -> List[str]:
    company = get_company_record(companies_df, company_id)
    frame_rows = []
    for _, student in student_features_df.iterrows():
        raw = students_df[students_df["student_id"] == student["student_id"]].iloc[0].to_dict()
        student_data = student.to_dict()
        student_data.update(raw)
        features = build_inference_features(student_data, company)
        features["student_id"] = student["student_id"]
        frame_rows.append(features)
    frame = pd.DataFrame(frame_rows)
    scores = ranker.predict(ranker_scaler.transform(frame[ranker_feat_cols].fillna(0)))
    shortlist = (
        pd.DataFrame({"student_id": frame["student_id"], "score": scores})
        .sort_values("score", ascending=False)
        .head(top_k)["student_id"]
        .tolist()
    )
    return shortlist


def fairness_comparison(
    company_id: str,
    students_df: pd.DataFrame,
    companies_df: pd.DataFrame,
    student_features_df: pd.DataFrame,
    ranker: Any = None,
    ranker_scaler: Any = None,
    ranker_feat_cols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    feature_df = build_company_feature_matrix(company_id, students_df, companies_df, student_features_df)
    labels = load_training_labels()
    company_labels = labels[labels["company_id"] == company_id][["student_id", "eligible"]]
    audit = feature_df.merge(company_labels, on="student_id", how="left")
    audit["eligible"] = audit["eligible"].fillna(0).astype(int)
    audit = audit.merge(students_df[["student_id", "gender", "full_name", "department", "cgpa"]], on="student_id", how="left")

    reference_shortlist = []
    if ranker is not None and ranker_scaler is not None and ranker_feat_cols:
        try:
            reference_shortlist = ranker_shortlist_for_company(
                company_id, students_df, student_features_df, companies_df, ranker, ranker_scaler, ranker_feat_cols
            )
        except Exception:
            reference_shortlist = []

    response_variants = []
    for key in ["baseline", "champion", "tightened"]:
        try:
            artifact = load_variant_artifact(key)
        except FileNotFoundError as exc:
            response_variants.append({
                "key": key,
                "label": FAIRNESS_ARTIFACTS[key]["label"],
                "available": False,
                "detail": str(exc),
            })
            continue

        X = audit[artifact["feature_cols"]].fillna(0)
        X_scaled = artifact["scaler"].transform(X)
        probabilities = artifact["model"].predict_proba(X_scaled)[:, 1]
        predictions = (probabilities >= 0.5).astype(int)

        shortlist_df = audit.assign(score=probabilities).sort_values("score", ascending=False).head(20)
        shortlist = shortlist_df[["student_id", "full_name", "department", "cgpa"]].assign(score=shortlist_df["score"].round(4))

        response_variants.append({
            "key": key,
            "label": artifact["label"],
            "available": True,
            "accuracy": round(float(accuracy_score(audit["eligible"], predictions)), 4),
            "f1": round(float(f1_score(audit["eligible"], predictions, zero_division=0)), 4),
            "delta_dp": round(demographic_parity_gap(predictions, audit["gender"]), 4),
            "delta_eo": round(equalized_odds_gap(audit["eligible"].to_numpy(), predictions, audit["gender"]), 4),
            "shortlist_overlap": round(shortlist_overlap(reference_shortlist, shortlist["student_id"].tolist()), 4),
            "shortlist": shortlist.to_dict(orient="records"),
        })

    return clean_nan({
        "company_id": company_id,
        "reference_shortlist": reference_shortlist,
        "variants": response_variants,
    })


def parse_iso(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def retrain_constrained_model(
    company_id: str,
    epsilon: float,
    students_df: pd.DataFrame,
    companies_df: pd.DataFrame,
    student_features_df: pd.DataFrame,
    triggered_by: str,
) -> Dict[str, Any]:
    if epsilon < 0.001 or epsilon > 0.05:
        raise ValueError("epsilon must be between 0.001 and 0.05")

    try:
        import lightgbm as lgb  # type: ignore
        from fairlearn.reductions import DemographicParity, ExponentiatedGradient  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"Fairlearn retraining dependencies are unavailable: {exc}")

    persistence = get_persistence_client()
    if persistence.available and persistence.client is not None:
        try:
            recent = (
                persistence.client.table("model_fairness_history")
                .select("trained_at")
                .eq("company_id", company_id)
                .order("trained_at", desc=True)
                .limit(1)
                .execute()
            )
            if recent.data:
                last_trained = parse_iso(recent.data[0]["trained_at"])
                if datetime.now(timezone.utc) - last_trained < timedelta(hours=1):
                    raise PermissionError("This company can only be retrained once per hour.")
        except PermissionError:
            raise
        except Exception:
            persistence = PersistenceStatus(False, "Supabase unavailable")
    else:
        history = [item for item in read_local_records(LOCAL_FAIRNESS_HISTORY_PATH) if item["company_id"] == company_id]
        if history:
            last_trained = parse_iso(history[-1]["trained_at"])
            if datetime.now(timezone.utc) - last_trained < timedelta(hours=1):
                raise PermissionError("This company can only be retrained once per hour.")

    company = get_company_record(companies_df, company_id)
    frame = build_bias_frame(students_df, student_features_df)
    hard_pass = apply_rule_mask(frame, company)
    eligible_students = frame.loc[hard_pass, "student_id"].tolist()
    if len(eligible_students) < 20:
        raise RuntimeError("Not enough Layer-1 eligible students are available to retrain a constrained model.")

    feature_df = build_company_feature_matrix(company_id, students_df, companies_df, student_features_df)
    labels = load_training_labels()
    training = feature_df.merge(labels[labels["company_id"] == company_id][["student_id", "eligible"]], on="student_id", how="inner")
    training = training[training["student_id"].isin(eligible_students)]
    training = training.merge(students_df[["student_id", "gender"]], on="student_id", how="left")
    if training["eligible"].nunique() < 2:
        raise RuntimeError("The filtered training pool does not contain both classes after Layer-1 gating.")

    feature_cols = [col for col in training.columns if col not in {"student_id", "eligible", "gender"}]
    X = training[feature_cols].fillna(0)
    y = training["eligible"].astype(int)
    sensitive = training["gender"].fillna("Unknown").astype(str)

    X_train, X_test, y_train, y_test, sens_train, sens_test = train_test_split(
        X, y, sensitive, test_size=0.25, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    start = time.perf_counter()
    base_model = lgb.LGBMClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        random_state=42,
        verbose=-1,
    )
    fair_model = ExponentiatedGradient(
        base_model,
        constraints=DemographicParity(),
        eps=epsilon,
        max_iter=15,
    )
    fair_model.fit(X_train_scaled, y_train, sensitive_features=sens_train)
    train_seconds = time.perf_counter() - start

    probabilities = fair_model._pmf_predict(X_test_scaled)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    delta_dp = demographic_parity_gap(predictions, sens_test.reset_index(drop=True))
    delta_eo = equalized_odds_gap(y_test.to_numpy(), predictions, sens_test.reset_index(drop=True))
    accuracy = accuracy_score(y_test, predictions)
    f1 = f1_score(y_test, predictions, zero_division=0)

    bundle_name = f"fairlearn_lightgbm_eps_{epsilon:.3f}.pkl".replace(".000", ".0")
    bundle_path = os.path.join(MODEL_DIR, bundle_name)
    with open(bundle_path, "wb") as bundle_file:
        pickle.dump({"model": fair_model, "scaler": scaler, "feature_cols": feature_cols, "epsilon": epsilon}, bundle_file)

    history_record = {
        "id": int(time.time() * 1000),
        "company_id": company_id,
        "epsilon": epsilon,
        "accuracy": round(float(accuracy), 4),
        "f1": round(float(f1), 4),
        "delta_dp": round(float(delta_dp), 4),
        "delta_eo": round(float(delta_eo), 4),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "triggered_by": triggered_by,
    }
    if persistence.available and persistence.client is not None:
        try:
            persistence.client.table("model_fairness_history").insert(history_record).execute()
            history_record["persistence_mode"] = "supabase"
        except Exception:
            records = read_local_records(LOCAL_FAIRNESS_HISTORY_PATH)
            history_record["persistence_mode"] = "local"
            records.append(history_record)
            write_local_records(LOCAL_FAIRNESS_HISTORY_PATH, records)
    else:
        records = read_local_records(LOCAL_FAIRNESS_HISTORY_PATH)
        history_record["persistence_mode"] = "local"
        records.append(history_record)
        write_local_records(LOCAL_FAIRNESS_HISTORY_PATH, records)

    return clean_nan({
        **history_record,
        "training_time_seconds": round(float(train_seconds), 2),
        "artifact_path": bundle_name,
    })


def get_fairness_history(company_id: str) -> Dict[str, Any]:
    persistence = get_persistence_client()
    if persistence.available and persistence.client is not None:
        try:
            response = (
                persistence.client.table("model_fairness_history")
                .select("*")
                .eq("company_id", company_id)
                .order("trained_at")
                .execute()
            )
            return clean_nan({
                "company_id": company_id,
                "history": response.data or [],
                "persistence_mode": "supabase",
            })
        except Exception:
            pass

    local_history = [item for item in read_local_records(LOCAL_FAIRNESS_HISTORY_PATH) if item["company_id"] == company_id]
    return clean_nan({
        "company_id": company_id,
        "history": local_history,
        "persistence_mode": "local",
    })
