"""
Skill Recommender — Option 2: Surrogate Model

Trains a surrogate regression model that predicts the eligibility gain
a student would get from adding a specific skill — WITHOUT running all
50 company simulations at inference time.

Input features (per student-skill pair):
  • Student aggregate profile (academic + experience + skills)
  • Skill identity (one-hot or label encoded)
  • Current skill count, gap metrics

Target:
  • avg_eligibility_gain from skill_gap_labels.csv

Output:
  • models/skill_recommender.pkl
  • models/skill_recommender_scaler.pkl
  • models/skill_recommender_metrics.json

At inference: given a new student profile + a candidate skill,
predict expected gain in O(1) instead of O(50 companies).
"""

import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

_HERE     = os.path.dirname(__file__)
DATA_DIR  = os.path.join(_HERE, "..", "..", "data")
MODEL_DIR = os.path.join(_HERE, "..", "..", "models")

# Student aggregate features (bias-free)
STUDENT_FEAT_COLS = [
    "cgpa_normalized", "10th_normalized", "12th_normalized",
    "active_backlogs", "total_internship_months", "max_internship_tier",
    "num_projects", "max_project_complexity",
    "num_global_premium_certs", "num_global_standard_certs",
    "num_national_certs", "max_cert_tier",
    "num_papers", "max_paper_tier",
    "num_advanced_skills", "num_verified_skills",
    "dept_match_ratio", "n_skills_currently", "baseline_avg_prob",
]


def build_surrogate_features(gap_df: pd.DataFrame,
                              pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Merge gap labels with student aggregate features to build the
    surrogate model's input matrix.
    """
    # Aggregate student features from pair_features (take first row per student)
    student_agg = pairs.groupby("student_id").first().reset_index()
    student_agg["cgpa_normalized"] = student_agg["cgpa_normalized"]
    dept_match_ratio = (
        pairs.groupby("student_id")["dept_match"]
        .mean()
        .reset_index()
        .rename(columns={"dept_match": "dept_match_ratio"})
    )
    student_agg = student_agg.drop(columns=["dept_match_ratio"], errors="ignore")
    student_agg = student_agg.merge(dept_match_ratio, on="student_id", how="left")

    # Encode skill name as integer (label encoding)
    le = LabelEncoder()
    gap_df = gap_df.copy()
    gap_df["skill_encoded"] = le.fit_transform(gap_df["candidate_skill"])

    merged = gap_df.merge(
        student_agg[["student_id"] + [c for c in STUDENT_FEAT_COLS
                                       if c in student_agg.columns and
                                       c not in gap_df.columns]],
        on="student_id", how="left",
    )

    # n_skills_currently and baseline_avg_prob come from gap_df itself
    for col in ["n_skills_currently", "baseline_avg_prob"]:
        if col not in merged.columns:
            merged[col] = 0

    return merged, le


def evaluate_surrogate(y_true, y_pred, prefix="test") -> dict:
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2   = r2_score(y_true, y_pred)
    rho, _ = spearmanr(y_true, y_pred)
    metrics = {
        f"{prefix}_mae":     round(mae,  6),
        f"{prefix}_rmse":    round(rmse, 6),
        f"{prefix}_r2":      round(r2,   4),
        f"{prefix}_spearman_rho": round(float(rho), 4),
    }
    return metrics


def train_skill_recommender() -> dict:
    os.makedirs(MODEL_DIR, exist_ok=True)

    print("=" * 60)
    print("  Option 2 — Skill Recommender (Surrogate Model)")
    print("=" * 60)

    gap_df = pd.read_csv(os.path.join(DATA_DIR, "skill_gap_labels.csv"))
    pairs  = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))

    print(f"\n📂  Loaded {len(gap_df):,} (student, skill) training samples")
    print(f"    Students: {gap_df['student_id'].nunique()}")
    print(f"    Skills:   {gap_df['candidate_skill'].nunique()}")
    print(f"    Avg gain: {gap_df['avg_eligibility_gain'].mean():.4f}")

    # Build feature matrix
    merged, le = build_surrogate_features(gap_df, pairs)

    feat_cols = ["skill_encoded"] + [c for c in STUDENT_FEAT_COLS if c in merged.columns]
    X = merged[feat_cols].fillna(0)
    y = merged["avg_eligibility_gain"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    print("\n🚀  Training Gradient Boosting Regressor …")
    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train_s, y_train)

    y_pred = model.predict(X_test_s)
    metrics = evaluate_surrogate(y_test, y_pred)

    print("\n📊  Surrogate Model Performance:")
    print(f"   MAE:          {metrics['test_mae']:.6f}")
    print(f"   RMSE:         {metrics['test_rmse']:.6f}")
    print(f"   R²:           {metrics['test_r2']:.4f}")
    print(f"   Spearman ρ:   {metrics['test_spearman_rho']:.4f}  "
          f"({'✅ Good (>0.8)' if metrics['test_spearman_rho'] > 0.8 else '⚠️  Check simulation quality'})")

    # Feature importance
    importance = model.feature_importances_
    imp_pairs = sorted(zip(feat_cols, importance), key=lambda x: x[1], reverse=True)
    print("\n🔍  Feature Importance (top 8):")
    for feat, imp in imp_pairs[:8]:
        print(f"   {feat:35s} {imp:.4f}")

    # Save
    model_path  = os.path.join(MODEL_DIR, "skill_recommender.pkl")
    scaler_path = os.path.join(MODEL_DIR, "skill_recommender_scaler.pkl")
    le_path     = os.path.join(MODEL_DIR, "skill_recommender_label_encoder.pkl")
    feats_path  = os.path.join(MODEL_DIR, "skill_recommender_features.json")
    metrics_path = os.path.join(MODEL_DIR, "skill_recommender_metrics.json")

    with open(model_path,  "wb") as f: pickle.dump(model,  f)
    with open(scaler_path, "wb") as f: pickle.dump(scaler, f)
    with open(le_path,     "wb") as f: pickle.dump(le,     f)
    with open(feats_path,  "w")  as f: json.dump(feat_cols, f, indent=2)
    with open(metrics_path,"w")  as f: json.dump(metrics,   f, indent=2)

    print(f"\n💾  Recommender saved → {model_path}")
    return metrics


def recommend_skills(student_id: str,
                     top_k: int = 5,
                     use_surrogate: bool = True) -> list[dict]:
    """
    Return top-K skill recommendations for a student.
    If use_surrogate=True  → O(|ALL_SKILLS|) surrogate predictions
    If use_surrogate=False → read directly from skill_gap_labels.csv (ground truth)
    """
    if use_surrogate:
        with open(os.path.join(MODEL_DIR, "skill_recommender.pkl"),               "rb") as f: mdl = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "skill_recommender_scaler.pkl"),        "rb") as f: scl = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "skill_recommender_label_encoder.pkl"), "rb") as f: le  = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "skill_recommender_features.json"))          as f: fc  = json.load(f)

        pairs = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))
        student_rows = pairs[pairs["student_id"] == student_id]
        student_row = student_rows.iloc[0]
        dept_match_ratio = float(student_rows["dept_match"].mean()) if "dept_match" in student_rows else 0.0

        rows = []
        for skill in le.classes_:
            skill_enc = le.transform([skill])[0]
            feats = {"skill_encoded": skill_enc}
            for col in fc:
                if col != "skill_encoded":
                    feats[col] = dept_match_ratio if col == "dept_match_ratio" else student_row.get(col, 0)
            X = pd.DataFrame([feats])[fc].fillna(0)
            gain = float(mdl.predict(scl.transform(X))[0])
            rows.append({"skill": skill, "predicted_gain": round(gain, 4)})

        return sorted(rows, key=lambda x: x["predicted_gain"], reverse=True)[:top_k]

    else:
        gap_df = pd.read_csv(os.path.join(DATA_DIR, "skill_gap_labels.csv"))
        student_df = gap_df[gap_df["student_id"] == student_id].copy()
        student_df = student_df.sort_values("avg_eligibility_gain", ascending=False)
        return student_df.head(top_k)[
            ["candidate_skill", "avg_eligibility_gain", "max_eligibility_gain", "n_companies_gained"]
        ].rename(columns={"candidate_skill": "skill",
                           "avg_eligibility_gain": "predicted_gain"}).to_dict(orient="records")


if __name__ == "__main__":
    train_skill_recommender()
