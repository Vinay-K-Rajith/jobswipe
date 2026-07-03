"""
Run Skill Gap — Option 2: End-to-end runner

Step 1 → Simulate counterfactual skill gains (skill_gap_labels.csv)
Step 2 → Train surrogate Gradient Boosting recommender
Step 3 → Demo: show top-K skill recommendations for sample students

Usage (from backend/):
    python -m src.model.run_skill_gap
    python -m src.model.run_skill_gap --students 100   # quick test with 100 students
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.model.skill_gap_simulator import run_simulation
from src.model.skill_recommender   import recommend_skills, train_skill_recommender

import pandas as pd


def demo_recommendations(student_ids: list[str], top_k: int = 5):
    """Print skill recommendations for a list of students."""
    students = pd.read_csv(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "students.csv")
    )
    id_to_name = dict(zip(students["student_id"], students["full_name"]))

    for sid in student_ids:
        name = id_to_name.get(sid, sid)
        print(f"\n👤  {name} ({sid})")

        # Ground-truth (from simulation)
        gt_recs = recommend_skills(sid, top_k=top_k, use_surrogate=False)
        print(f"   📋 Ground-truth top-{top_k} (from simulation):")
        for i, r in enumerate(gt_recs, 1):
            gain_str = f"{r['predicted_gain']:+.4f}"
            n_comp   = r.get("n_companies_gained", "?")
            print(f"      {i}. {r['skill']:25s}  Δgain={gain_str}  ({n_comp} companies)")

        # Surrogate prediction
        try:
            surr_recs = recommend_skills(sid, top_k=top_k, use_surrogate=True)
            print(f"   🤖 Surrogate top-{top_k} (model prediction):")
            for i, r in enumerate(surr_recs, 1):
                gain_str = f"{r['predicted_gain']:+.4f}"
                print(f"      {i}. {r['skill']:25s}  Δgain={gain_str}")
        except Exception as e:
            print(f"   ⚠️  Surrogate not available: {e}")


def main():
    parser = argparse.ArgumentParser(description="Option 2 — Skill Gap Pipeline")
    parser.add_argument("--students", type=int, default=None,
                        help="Limit simulation to N students (default: all)")
    parser.add_argument("--demo-ids", nargs="*", default=None,
                        help="Student IDs for demo (default: first 3 in dataset)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  OPTION 2 — Skill Gap Prediction Pipeline")
    print("=" * 60)

    # Step 1: Simulate
    print("\n── STEP 1: Counterfactual Skill Simulation ───────────────────")
    gap_df = run_simulation(max_students=args.students)

    # Step 2: Train surrogate
    print("\n── STEP 2: Train Surrogate Recommender ───────────────────────")
    metrics = train_skill_recommender()

    # Step 3: Demo
    print("\n── STEP 3: Demo Skill Recommendations ───────────────────────")
    if args.demo_ids:
        demo_ids = args.demo_ids
    else:
        # Pick first 3 students that appear in gap labels
        demo_ids = gap_df["student_id"].unique()[:3].tolist()

    demo_recommendations(demo_ids, top_k=5)

    print("\n" + "=" * 60)
    print("  ✅  Option 2 Complete")
    print(f"     Spearman ρ (surrogate vs simulation): "
          f"{metrics.get('test_spearman_rho', 'N/A')}")
    print("     Artifacts in backend/models/")
    print("=" * 60)


if __name__ == "__main__":
    main()
