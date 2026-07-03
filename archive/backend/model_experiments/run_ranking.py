"""
Run Ranking — Option 1: End-to-end runner

Executes the full Learning-to-Rank pipeline in sequence:
  Step 1  → Generate continuous fit-score labels (ranking_labels.csv)
  Step 2  → Train XGBoost ranker (rank:ndcg)
  Step 3  → Evaluate: NDCG@K, Precision@K, Kendall's τ, Fairness Gap
  Step 4  → Demo: show ranked shortlist for a sample company

Usage (from backend/):
    python -m src.model.run_ranking
"""

import os
import sys

# Ensure project root is on the path when run as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.model.rank_label_generator import generate_rank_labels
from src.model.rank_train           import load_ranking_data, train_ranker
from src.model.rank_evaluate        import run_evaluation, load_all


def demo_shortlist(company_id: str = "CO001", top_k: int = 10):
    """Print the ranked shortlist for one company."""
    import json, pickle, pandas as pd

    MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
    DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "data")

    with open(os.path.join(MODEL_DIR, "ranker.pkl"),              "rb") as f: ranker = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "ranker_scaler.pkl"),       "rb") as f: scaler = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "ranker_feature_columns.json"))    as f: feat_cols = json.load(f)

    pairs    = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))
    labels   = pd.read_csv(os.path.join(DATA_DIR, "ranking_labels.csv"))
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))
    companies = pd.read_csv(os.path.join(DATA_DIR, "companies.csv"))

    company = companies[companies["company_id"] == company_id].iloc[0]
    cdf = pairs[pairs["company_id"] == company_id].copy()

    X = cdf[feat_cols].fillna(0)
    cdf["rank_score"] = ranker.predict(scaler.transform(X))
    cdf = cdf.merge(labels[["student_id","company_id","fit_score","eligible"]],
                    on=["student_id","company_id"])
    cdf = cdf.merge(students[["student_id","full_name","department","cgpa"]], on="student_id")
    cdf = cdf.sort_values("rank_score", ascending=False)

    print(f"\nCompany: {company['company_name']} ({company_id}) - {company['tier']}")
    print(f"    Min CGPA: {company['min_cgpa']} | Dept: {company['allowed_departments']}")
    print(f"\nTop-{top_k} Ranked Shortlist:")
    print(f"   {'Rank':>4}  {'Student':20s}  {'Dept':6}  {'CGPA':5}  {'FitScore':8}  {'Eligible':8}")
    print("   " + "-" * 62)
    for i, (_, row) in enumerate(cdf.head(top_k).iterrows(), 1):
        elig = "YES" if row["eligible"] == 1 else "NO"
        print(f"   {i:>4}  {row['full_name']:20s}  {row['department']:6}  "
              f"{row['cgpa']:5.2f}  {row['fit_score']:8.4f}  {elig}")


def main():
    print("\n" + "=" * 60)
    print("  OPTION 1 - Learning-to-Rank Pipeline")
    print("=" * 60)

    # Step 1: Labels
    print("\n-- STEP 1: Generate Ranking Labels --")
    generate_rank_labels()

    # Step 2: Train
    print("\n-- STEP 2: Train XGBoost Ranker --")
    data = load_ranking_data()
    print(f"   Loaded {len(data):,} pairs across {data['group_id'].nunique()} query groups")
    train_ranker(data)

    # Step 3: Evaluate
    print("\n-- STEP 3: Evaluate Ranker --")
    run_evaluation()

    # Step 4: Demo
    print("\n-- STEP 4: Demo Shortlist --")
    demo_shortlist(company_id="CO001", top_k=10)

    print("\n" + "=" * 60)
    print("  [OK] Option 1 Complete - artifacts in backend/models/")
    print("=" * 60)


if __name__ == "__main__":
    main()
