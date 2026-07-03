"""
Rank Evaluate — Option 1: Learning-to-Rank

Comprehensive evaluation of the trained XGBoost ranker.
Computes:
  • NDCG@K (K = 5, 10, 20) — primary ranking quality metric
  • Precision@K             — fraction of top-K that are truly fit
  • Kendall's τ             — ranking correlation with ground-truth order
  • Fairness Gap            — NDCG@10 gap between male/female student subsets
  • Per-company breakdown   — which companies rank best / worst

These metrics are unpublishable from a binary classifier — they are the
core research contribution of Option 1.
"""

import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


# ── Metric helpers ────────────────────────────────────────────────────────────

def dcg_at_k(relevances: np.ndarray, k: int) -> float:
    r = np.asarray(relevances, dtype=float)[:k]
    if r.size == 0:
        return 0.0
    return float(np.sum((2 ** r - 1) / np.log2(np.arange(2, r.size + 2))))


def ndcg_at_k(relevances: np.ndarray, k: int) -> float:
    ideal = dcg_at_k(np.sort(relevances)[::-1], k)
    return dcg_at_k(relevances, k) / ideal if ideal > 0 else 1.0


def precision_at_k(relevances: np.ndarray, k: int, threshold: int = 1) -> float:
    return float(np.mean(np.asarray(relevances)[:k] >= threshold))


def average_precision(relevances: np.ndarray, threshold: int = 1) -> float:
    """Mean Average Precision (MAP) — works with graded relevance."""
    hits, total = 0, 0
    ap = 0.0
    for i, r in enumerate(relevances, 1):
        if r >= threshold:
            hits += 1
            ap += hits / i
            total += 1
    return ap / total if total > 0 else 0.0


def kendall_tau_per_group(pred_scores: np.ndarray,
                           true_grades: np.ndarray) -> float:
    """Kendall's τ between predicted ranking and true relevance grade order."""
    if len(pred_scores) < 2:
        return 1.0
    tau, _ = kendalltau(pred_scores, true_grades)
    return float(tau) if not np.isnan(tau) else 0.0


# ── Loader ────────────────────────────────────────────────────────────────────

def load_all():
    with open(os.path.join(MODEL_DIR, "ranker.pkl"),  "rb") as f:
        ranker = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "ranker_scaler.pkl"), "rb") as f:
        scaler = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "ranker_feature_columns.json")) as f:
        feature_cols = json.load(f)

    pairs   = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))
    labels  = pd.read_csv(os.path.join(DATA_DIR, "ranking_labels.csv"))
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))

    df = pairs.merge(
        labels[["student_id", "company_id", "group_id",
                "relevance_grade", "fit_score", "eligible"]],
        on=["student_id", "company_id"],
    )
    # Attach gender for fairness analysis (audit only, NOT in model features)
    df = df.merge(students[["student_id", "gender"]], on="student_id")
    return ranker, scaler, feature_cols, df


# ── Main evaluation ───────────────────────────────────────────────────────────

def run_evaluation(top_k_list: list[int] | None = None) -> dict:
    if top_k_list is None:
        top_k_list = [5, 10, 20]

    print("=" * 60)
    print("  Option 1 — Ranking Evaluation Report")
    print("=" * 60)

    ranker, scaler, feature_cols, df = load_all()

    X = df[feature_cols].fillna(0)
    df["pred_score"] = ranker.predict(scaler.transform(X))

    # ── 1. Global ranking metrics ─────────────────────────────────────────────
    print("\n📊  1. GLOBAL RANKING METRICS (macro-avg over companies)")
    print("-" * 50)

    metric_accum = {f"ndcg@{k}": [] for k in top_k_list}
    metric_accum.update({f"precision@{k}": [] for k in top_k_list})
    metric_accum["map"] = []
    metric_accum["kendall_tau"] = []

    per_company_rows = []

    for company_id, grp in df.groupby("company_id"):
        grp_s = grp.sort_values("pred_score", ascending=False)
        rel   = grp_s["relevance_grade"].values

        row = {"company_id": company_id, "n_students": len(grp_s)}
        for k in top_k_list:
            ndcg = ndcg_at_k(rel, k)
            prec = precision_at_k(rel, k)
            metric_accum[f"ndcg@{k}"].append(ndcg)
            metric_accum[f"precision@{k}"].append(prec)
            row[f"ndcg@{k}"]      = round(ndcg, 4)
            row[f"precision@{k}"] = round(prec, 4)

        ap  = average_precision(rel)
        tau = kendall_tau_per_group(grp_s["pred_score"].values, rel)
        metric_accum["map"].append(ap)
        metric_accum["kendall_tau"].append(tau)
        row["map"]         = round(ap,  4)
        row["kendall_tau"] = round(tau, 4)
        per_company_rows.append(row)

    global_metrics = {k: float(np.mean(v)) for k, v in metric_accum.items()}
    global_metrics["num_companies"] = df["company_id"].nunique()
    global_metrics["num_students"]  = df["student_id"].nunique()

    for k, v in global_metrics.items():
        print(f"   {k:25s}: {v:.4f}")

    # ── 2. Fairness gap: NDCG@10 male vs female ───────────────────────────────
    print("\n📊  2. RANKING FAIRNESS GAP (NDCG@10 by gender)")
    print("-" * 50)

    fairness = {}
    for gender, gdf in df.groupby("gender"):
        ndcg_list = []
        for _, grp in gdf.groupby("company_id"):
            grp_s = grp.sort_values("pred_score", ascending=False)
            ndcg_list.append(ndcg_at_k(grp_s["relevance_grade"].values, 10))
        fairness[gender] = float(np.mean(ndcg_list))
        print(f"   {gender:15s}: NDCG@10 = {fairness[gender]:.4f}")

    gender_vals = list(fairness.values())
    ndcg_fairness_gap = max(gender_vals) - min(gender_vals) if len(gender_vals) > 1 else 0.0
    fairness["ndcg@10_fairness_gap"] = round(ndcg_fairness_gap, 4)
    print(f"   {'Fairness Gap':15s}: {ndcg_fairness_gap:.4f}  "
          f"({'✅ Good (<0.05)' if ndcg_fairness_gap < 0.05 else '⚠️  Review needed'})")

    # ── 3. Best / worst ranked companies ─────────────────────────────────────
    per_company_df = pd.DataFrame(per_company_rows).sort_values("ndcg@10", ascending=False)
    print("\n📊  3. TOP-5 COMPANIES BY NDCG@10")
    print("-" * 50)
    print(per_company_df.head(5).to_string(index=False))
    print("\n📊     BOTTOM-5 COMPANIES BY NDCG@10")
    print("-" * 50)
    print(per_company_df.tail(5).to_string(index=False))

    # ── 4. Save results ───────────────────────────────────────────────────────
    report = {
        "global_metrics":   global_metrics,
        "fairness_by_gender": fairness,
        "per_company": per_company_df.to_dict(orient="records"),
    }

    report_path   = os.path.join(MODEL_DIR, "ranking_evaluation.json")
    company_path  = os.path.join(MODEL_DIR, "ranking_per_company.csv")

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    per_company_df.to_csv(company_path, index=False)

    print(f"\n💾  Full report     → {report_path}")
    print(f"💾  Per-company CSV → {company_path}")
    print("\n✅  Evaluation complete.")
    return report


if __name__ == "__main__":
    run_evaluation()
