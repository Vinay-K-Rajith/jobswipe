"""
Option 1: Learning-to-rank training.

Each company is treated as one ranking query. Evaluation uses GroupKFold so
complete companies are held out per fold, avoiding the suspicious single split
where a tiny test set can report perfect NDCG.
"""

import json
import os
import pickle

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")

FEATURE_COLS = [
    "cgpa_normalized",
    "10th_normalized",
    "12th_normalized",
    "active_backlogs",
    "dept_match",
    "required_skills_match_ratio",
    "preferred_skills_match_ratio",
    "total_internship_months",
    "max_internship_tier",
    "num_projects",
    "max_project_complexity",
    "meets_project_complexity",
    "num_global_premium_certs",
    "num_global_standard_certs",
    "num_national_certs",
    "meets_cert_tier",
    "num_papers",
    "max_paper_tier",
    "num_advanced_skills",
    "num_verified_skills",
]


def load_ranking_data():
    """Load pair features merged with ranking labels."""
    pairs = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))
    labels = pd.read_csv(os.path.join(DATA_DIR, "ranking_labels.csv"))

    data = pairs.merge(
        labels[
            [
                "student_id",
                "company_id",
                "group_id",
                "fit_score",
                "relevance_grade",
                "rank_within_group",
            ]
        ],
        on=["student_id", "company_id"],
    )
    return data.sort_values("group_id").reset_index(drop=True)


def build_group_array(data: pd.DataFrame) -> np.ndarray:
    """Return group sizes required by XGBoost ranker."""
    return data.groupby("group_id", sort=True).size().values


def make_ranker(random_state: int):
    return xgb.XGBRanker(
        objective="rank:ndcg",
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=random_state,
        tree_method="hist",
        eval_metric="ndcg@10",
    )


def fit_ranker_fold(
    data: pd.DataFrame,
    X: pd.DataFrame,
    train_idx: np.ndarray,
    random_state: int,
):
    train_sorted = data.iloc[train_idx].sort_values("group_id")
    train_sort_idx = train_sorted.index

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X.loc[train_sort_idx].fillna(0))
    y_train = data.loc[train_sort_idx, "relevance_grade"].values
    group_train = build_group_array(data.loc[train_sort_idx])

    ranker = make_ranker(random_state)
    ranker.fit(X_train_s, y_train, group=group_train, verbose=False)
    return ranker, scaler


def train_ranker(
    data: pd.DataFrame,
    n_splits: int = 5,
    random_state: int = 42,
):
    """
    Evaluate with company-level GroupKFold, then train the saved serving model
    on all companies.
    """
    if not HAS_XGB:
        raise ImportError("XGBoost is required. Install it with: pip install xgboost")

    os.makedirs(MODEL_DIR, exist_ok=True)

    X = data[FEATURE_COLS].fillna(0)
    y = data["relevance_grade"].values
    groups = data["group_id"].values

    print(f"Cross-validating XGBoost ranker with GroupKFold({n_splits}) ...")
    fold_metrics = []
    gkf = GroupKFold(n_splits=n_splits)
    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups), 1):
        fold_ranker, fold_scaler = fit_ranker_fold(
            data=data,
            X=X,
            train_idx=train_idx,
            random_state=random_state + fold,
        )

        test_sorted = data.iloc[test_idx].sort_values("group_id")
        test_sort_idx = test_sorted.index
        X_test_s = fold_scaler.transform(X.loc[test_sort_idx].fillna(0))
        y_test = data.loc[test_sort_idx, "relevance_grade"].values
        scores = fold_ranker.predict(X_test_s)

        test_df = data.loc[test_sort_idx].copy()
        test_df["pred_score"] = scores
        test_df["true_grade"] = y_test

        result = evaluate_ranker(test_df)
        result["fold"] = fold
        fold_metrics.append(result)

    metrics = summarize_cv_metrics(fold_metrics)

    print("\nRanking metrics (company-level GroupKFold CV):")
    for key, value in metrics.items():
        if key == "folds":
            continue
        if isinstance(value, float):
            print(f"   {key:30s}: {value:.4f}")
        else:
            print(f"   {key:30s}: {value}")

    print("\nFitting final serving ranker on all companies ...")
    ranker, scaler = fit_ranker_fold(
        data=data,
        X=X,
        train_idx=np.arange(len(data)),
        random_state=random_state,
    )

    importance = ranker.feature_importances_
    feat_imp = sorted(zip(FEATURE_COLS, importance), key=lambda item: item[1], reverse=True)
    print("\nFeature importance (top 10):")
    for feat, imp in feat_imp[:10]:
        print(f"   {feat:40s} {imp:.4f}")

    ranker_path = os.path.join(MODEL_DIR, "ranker.pkl")
    rscaler_path = os.path.join(MODEL_DIR, "ranker_scaler.pkl")
    rfeats_path = os.path.join(MODEL_DIR, "ranker_feature_columns.json")
    rmetrics_path = os.path.join(MODEL_DIR, "ranker_metrics.json")

    with open(ranker_path, "wb") as f:
        pickle.dump(ranker, f)
    with open(rscaler_path, "wb") as f:
        pickle.dump(scaler, f)
    with open(rfeats_path, "w") as f:
        json.dump(FEATURE_COLS, f, indent=2)
    with open(rmetrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    ranking_eval_path = os.path.join(MODEL_DIR, "ranking_evaluation.json")
    if os.path.exists(ranking_eval_path):
        with open(ranking_eval_path) as f:
            rank_eval = json.load(f)
        with open(rmetrics_path) as f:
            existing = json.load(f)
        existing["fairness_by_gender"] = rank_eval.get("fairness_by_gender", {})
        existing["ndcg_fairness_gap"] = existing["fairness_by_gender"].get("ndcg@10_fairness_gap")
        with open(rmetrics_path, "w") as f:
            json.dump(existing, f, indent=2)
        if existing["ndcg_fairness_gap"] is not None:
            print(f"Merged NDCG fairness gap: {existing['ndcg_fairness_gap']:.4f}")

    print(f"\nRanker saved  -> {ranker_path}")
    print(f"Scaler saved  -> {rscaler_path}")
    print(f"Metrics saved -> {rmetrics_path}")

    return ranker, scaler, metrics


def dcg_at_k(relevances: np.ndarray, k: int) -> float:
    """Discounted cumulative gain at k."""
    r = np.asarray(relevances, dtype=float)[:k]
    if r.size == 0:
        return 0.0
    discounts = np.log2(np.arange(2, r.size + 2))
    return float(np.sum((2 ** r - 1) / discounts))


def ndcg_at_k(relevances: np.ndarray, k: int) -> float:
    """Normalized discounted cumulative gain at k."""
    ideal = dcg_at_k(np.sort(relevances)[::-1], k)
    if ideal == 0:
        return 1.0
    return dcg_at_k(relevances, k) / ideal


def precision_at_k(relevances: np.ndarray, k: int, threshold: int = 1) -> float:
    """Fraction of top-k with relevance >= threshold."""
    top_k = np.asarray(relevances)[:k]
    return float(np.mean(top_k >= threshold))


def evaluate_ranker(test_df: pd.DataFrame) -> dict:
    """Compute per-company ranking metrics and macro-average them."""
    ndcg5_list, ndcg10_list, p5_list, p10_list = [], [], [], []

    for _, grp in test_df.groupby("company_id"):
        grp_sorted = grp.sort_values("pred_score", ascending=False)
        rel = grp_sorted["true_grade"].values

        ndcg5_list.append(ndcg_at_k(rel, 5))
        ndcg10_list.append(ndcg_at_k(rel, 10))
        p5_list.append(precision_at_k(rel, 5))
        p10_list.append(precision_at_k(rel, 10))

    return {
        "ndcg@5": float(np.mean(ndcg5_list)),
        "ndcg@10": float(np.mean(ndcg10_list)),
        "precision@5": float(np.mean(p5_list)),
        "precision@10": float(np.mean(p10_list)),
        "num_queries": int(len(ndcg5_list)),
    }


def summarize_cv_metrics(fold_metrics: list[dict]) -> dict:
    """Return mean/std metrics while preserving legacy mean keys."""
    metric_names = ["ndcg@5", "ndcg@10", "precision@5", "precision@10"]
    summary = {}
    for name in metric_names:
        values = np.array([fold[name] for fold in fold_metrics], dtype=float)
        summary[name] = float(values.mean())
        summary[f"{name}_mean"] = float(values.mean())
        summary[f"{name}_std"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0

    summary["num_folds"] = len(fold_metrics)
    summary["num_queries"] = int(sum(fold["num_queries"] for fold in fold_metrics))
    summary["folds"] = fold_metrics
    return summary


if __name__ == "__main__":
    print("=" * 60)
    print("  Option 1 - XGBoost Learning-to-Rank Training")
    print("=" * 60)

    ranking_data = load_ranking_data()
    print(
        f"\nLoaded {len(ranking_data):,} pairs across "
        f"{ranking_data['group_id'].nunique()} companies"
    )

    train_ranker(ranking_data)
    print("\nTraining complete.")
