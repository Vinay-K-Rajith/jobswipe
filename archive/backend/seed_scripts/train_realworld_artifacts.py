"""
Train isolated model artifacts for the real-world resume dataset.

Inputs:
  backend/data/resume_realworld_normalized/*.csv

Outputs:
  backend/models/resume_realworld_*.pkl/json
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score
from sklearn.model_selection import GroupKFold, StratifiedKFold, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from src.model.rank_train import FEATURE_COLS as RANKER_FEATURE_COLS, build_group_array, evaluate_ranker, make_ranker, summarize_cv_metrics
from src.model.skill_gap_simulator import ALL_SKILLS, simulate_student
from src.model.skill_recommender import STUDENT_FEAT_COLS, build_surrogate_features
from src.model.train import FEATURE_COLS as CLASSIFIER_FEATURE_COLS, make_classifier

try:
    import lightgbm as lgb  # type: ignore
    from fairlearn.reductions import DemographicParity, ExponentiatedGradient  # type: ignore
except Exception:
    lgb = None
    DemographicParity = None
    ExponentiatedGradient = None

DATA_DIR = BACKEND_DIR / "data" / "resume_realworld_normalized"
MODEL_DIR = BACKEND_DIR / "models"
PREFIX = "resume_realworld"


def save_pickle(name: str, payload: Any) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with (MODEL_DIR / name).open("wb") as handle:
        pickle.dump(payload, handle)


def save_json(name: str, payload: Any) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with (MODEL_DIR / name).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def load_training_data() -> pd.DataFrame:
    pairs = pd.read_csv(DATA_DIR / "pair_features.csv")
    labels = pd.read_csv(DATA_DIR / "training_labels.csv")
    return pairs.merge(labels[["student_id", "company_id", "eligible"]], on=["student_id", "company_id"])


def load_ranking_data() -> pd.DataFrame:
    pairs = pd.read_csv(DATA_DIR / "pair_features.csv")
    labels = pd.read_csv(DATA_DIR / "ranking_labels.csv")
    return pairs.merge(
        labels[["student_id", "company_id", "group_id", "fit_score", "relevance_grade", "rank_within_group"]],
        on=["student_id", "company_id"],
    ).sort_values("group_id").reset_index(drop=True)


def train_baseline_classifier() -> Dict[str, Any]:
    data = load_training_data()
    X = data[CLASSIFIER_FEATURE_COLS].copy().fillna(0)
    y = data["eligible"].astype(int)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    folds: List[Dict[str, float]] = []
    for fold, (train_idx, test_idx) in enumerate(skf.split(X, y), 1):
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X.iloc[train_idx])
        X_test = scaler.transform(X.iloc[test_idx])
        model = make_classifier(random_state=42 + fold)
        model.fit(X_train, y.iloc[train_idx])
        pred = model.predict(X_test)
        folds.append({
            "fold": fold,
            "accuracy": float(accuracy_score(y.iloc[test_idx], pred)),
            "precision": float(precision_score(y.iloc[test_idx], pred, zero_division=0)),
            "recall": float(recall_score(y.iloc[test_idx], pred, zero_division=0)),
            "f1": float(f1_score(y.iloc[test_idx], pred, zero_division=0)),
        })

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = make_classifier(random_state=42)
    model.fit(X_scaled, y)
    fitted_pred = model.predict(X_scaled)
    metrics = {
        "trained_on": "resume_realworld",
        "num_pairs": int(len(data)),
        "num_students": int(data["student_id"].nunique()),
        "num_companies": int(data["company_id"].nunique()),
        "accuracy": float(accuracy_score(y, fitted_pred)),
        "precision": float(precision_score(y, fitted_pred, zero_division=0)),
        "recall": float(recall_score(y, fitted_pred, zero_division=0)),
        "f1": float(f1_score(y, fitted_pred, zero_division=0)),
        "cv_results": folds,
    }
    save_pickle(f"{PREFIX}_baseline_model.pkl", model)
    save_pickle(f"{PREFIX}_baseline_scaler.pkl", scaler)
    save_json(f"{PREFIX}_baseline_feature_columns.json", CLASSIFIER_FEATURE_COLS)
    save_json(f"{PREFIX}_baseline_metrics.json", metrics)
    return metrics


def train_fair_champion() -> Dict[str, Any]:
    if lgb is None or DemographicParity is None or ExponentiatedGradient is None:
        metrics = {"trained_on": "resume_realworld", "skipped": True, "reason": "fairlearn/lightgbm unavailable"}
        save_json(f"{PREFIX}_fair_champion_metrics.json", metrics)
        return metrics

    data = load_training_data().copy()
    students = pd.read_csv(DATA_DIR / "students.csv")[["student_id", "gender", "department"]]
    data = data.merge(students, on="student_id", how="left")
    X = data[CLASSIFIER_FEATURE_COLS].fillna(0)
    y = data["eligible"].astype(int)
    sensitive = data["department"].fillna("Unknown").astype(str)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    base = lgb.LGBMClassifier(n_estimators=200, max_depth=6, learning_rate=0.05, random_state=42, verbose=-1)
    model = ExponentiatedGradient(base, constraints=DemographicParity(), eps=0.01, max_iter=15)
    model.fit(X_scaled, y, sensitive_features=sensitive)
    pred = np.asarray(model.predict(X_scaled), dtype=int)
    metrics = {
        "trained_on": "resume_realworld",
        "accuracy": float(accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "epsilon": 0.01,
    }
    save_pickle(f"{PREFIX}_fair_champion.pkl", {
        "model": model,
        "scaler": scaler,
        "feature_cols": CLASSIFIER_FEATURE_COLS,
        "epsilon": 0.01,
        "trained_on": "resume_realworld",
    })
    save_json(f"{PREFIX}_fair_champion_metrics.json", metrics)
    return metrics


def train_ranker_artifact() -> Dict[str, Any]:
    data = load_ranking_data()
    X = data[RANKER_FEATURE_COLS].fillna(0)
    y = data["relevance_grade"].values
    groups = data["group_id"].values
    fold_metrics = []
    for fold, (train_idx, test_idx) in enumerate(GroupKFold(n_splits=5).split(X, y, groups), 1):
        train_sorted = data.iloc[train_idx].sort_values("group_id")
        train_sort_idx = train_sorted.index
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X.loc[train_sort_idx])
        ranker = make_ranker(42 + fold)
        ranker.fit(X_train, data.loc[train_sort_idx, "relevance_grade"].values, group=build_group_array(data.loc[train_sort_idx]), verbose=False)

        test_sorted = data.iloc[test_idx].sort_values("group_id")
        test_sort_idx = test_sorted.index
        test_df = data.loc[test_sort_idx].copy()
        test_df["pred_score"] = ranker.predict(scaler.transform(X.loc[test_sort_idx]))
        test_df["true_grade"] = data.loc[test_sort_idx, "relevance_grade"].values
        result = evaluate_ranker(test_df)
        result["fold"] = fold
        fold_metrics.append(result)

    metrics = summarize_cv_metrics(fold_metrics)
    metrics.update({
        "trained_on": "resume_realworld",
        "num_pairs": int(len(data)),
        "num_queries": int(data["group_id"].nunique()),
    })

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    ranker = make_ranker(42)
    ranker.fit(X_scaled, y, group=build_group_array(data), verbose=False)
    save_pickle(f"{PREFIX}_ranker.pkl", ranker)
    save_pickle(f"{PREFIX}_ranker_scaler.pkl", scaler)
    save_json(f"{PREFIX}_ranker_feature_columns.json", RANKER_FEATURE_COLS)
    save_json(f"{PREFIX}_ranker_metrics.json", metrics)
    return metrics


def run_skill_gap_simulation(max_students: int | None = None) -> pd.DataFrame:
    with (MODEL_DIR / f"{PREFIX}_baseline_model.pkl").open("rb") as handle:
        model = pickle.load(handle)
    with (MODEL_DIR / f"{PREFIX}_baseline_scaler.pkl").open("rb") as handle:
        scaler = pickle.load(handle)
    feat_cols = json.loads((MODEL_DIR / f"{PREFIX}_baseline_feature_columns.json").read_text(encoding="utf-8"))
    pairs = pd.read_csv(DATA_DIR / "pair_features.csv")
    companies = pd.read_csv(DATA_DIR / "companies.csv")
    skills_df = pd.read_csv(DATA_DIR / "skills.csv")
    skill_lists = skills_df.groupby("student_id")["skill_name"].apply(list).to_dict()
    company_order = pairs[["company_id"]].drop_duplicates().merge(companies, on="company_id")

    all_rows = []
    student_ids = pairs["student_id"].drop_duplicates().tolist()
    if max_students:
        student_ids = student_ids[:max_students]
    for sid in student_ids:
        student_pairs = pairs[pairs["student_id"] == sid].copy().reset_index(drop=True)
        rows = simulate_student(sid, student_pairs, company_order, skill_lists.get(sid, []), model, scaler, feat_cols)
        all_rows.extend(rows)
    result = pd.DataFrame(all_rows)
    result.to_csv(DATA_DIR / "skill_gap_labels.csv", index=False)
    return result


def train_skill_recommender_artifact() -> Dict[str, Any]:
    gap_df = pd.read_csv(DATA_DIR / "skill_gap_labels.csv")
    pairs = pd.read_csv(DATA_DIR / "pair_features.csv")
    merged, encoder = build_surrogate_features(gap_df, pairs)
    feat_cols = ["skill_encoded"] + [col for col in STUDENT_FEAT_COLS if col in merged.columns]
    X = merged[feat_cols].fillna(0)
    y = merged["avg_eligibility_gain"].values
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    model = GradientBoostingRegressor(n_estimators=200, max_depth=5, learning_rate=0.05, subsample=0.8, random_state=42)
    model.fit(X_train_scaled, y_train)
    pred = model.predict(X_test_scaled)
    rho, _ = spearmanr(y_test, pred)
    metrics = {
        "trained_on": "resume_realworld",
        "test_mae": round(float(mean_absolute_error(y_test, pred)), 6),
        "test_rmse": round(float(np.sqrt(mean_squared_error(y_test, pred))), 6),
        "test_r2": round(float(r2_score(y_test, pred)), 4),
        "test_spearman_rho": round(float(rho), 4),
    }
    save_pickle(f"{PREFIX}_skill_recommender.pkl", model)
    save_pickle(f"{PREFIX}_skill_recommender_scaler.pkl", scaler)
    save_pickle(f"{PREFIX}_skill_recommender_label_encoder.pkl", encoder)
    save_json(f"{PREFIX}_skill_recommender_features.json", feat_cols)
    save_json(f"{PREFIX}_skill_recommender_metrics.json", metrics)
    return metrics


def main(max_skill_gap_students: int | None = None) -> None:
    summary = {
        "baseline": train_baseline_classifier(),
        "fair_champion": train_fair_champion(),
        "ranker": train_ranker_artifact(),
    }
    gap_df = run_skill_gap_simulation(max_students=max_skill_gap_students)
    summary["skill_gap"] = {
        "rows": int(len(gap_df)),
        "students": int(gap_df["student_id"].nunique()),
        "candidate_skills": int(gap_df["candidate_skill"].nunique()) if not gap_df.empty else len(ALL_SKILLS),
    }
    summary["skill_recommender"] = train_skill_recommender_artifact()
    save_json(f"{PREFIX}_training_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
