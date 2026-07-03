"""
Run Bias Detection — Option 3: End-to-end runner

Executes the upstream criteria bias detection pipeline:
  Step 1 → Run Fisher's Exact / Chi-Square test on every company's hard rules
  Step 2 → Print flagged companies with disparity scores and p-values
  Step 3 → Print summary statistics for the IEEE paper

Usage (from backend/):
    python -m src.model.run_bias_detection
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.model.criteria_bias_detector import run_criteria_bias_detection

import pandas as pd
from app.services.data_paths import dataset_variant

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


def print_ieee_summary(report: dict):
    """Print a formatted summary suitable for documenting in a paper."""
    summary = report["summary"]
    flagged = report["flagged_companies"]

    print("\n" + "=" * 60)
    print("  📄  IEEE-READY RESULTS SUMMARY")
    print("=" * 60)

    print(f"""
Dataset
  Companies analysed : {summary['n_companies']}
  Student pool size  : {summary['student_pool_size']}
  Gender distribution: {', '.join(f"{k}={v:.1%}" for k,v in summary['gender_pool_dist'].items())}

Criteria Bias Detection
  Significance level : α = {summary['significance']}
  Disparity threshold: {summary['threshold']*100:.0f}%
  Companies flagged  : {summary['n_flagged']} / {summary['n_companies']} ({summary['flag_rate']*100:.1f}%)

Flagged Company Breakdown by Tier:""")

    if flagged:
        flagged_df = pd.DataFrame(flagged)
        tier_counts = flagged_df["tier"].value_counts()
        for tier, count in tier_counts.items():
            print(f"  {tier:10s}: {count} companies flagged")

        print(f"""
Top Bias-Driving Criteria (across flagged companies):""")
        criterion_counts = flagged_df["top_bias_criterion"].value_counts()
        for crit, count in criterion_counts.items():
            pct = count / len(flagged_df) * 100
            print(f"  {crit:12s}: {count} companies ({pct:.0f}%)")

        print(f"""
Highest-Disparity Companies:
  {'Company':35s} {'Tier':8s} {'Disparity':10s} {'p-value':10s} {'Driver'}""")
        print("  " + "-" * 75)
        for f in sorted(flagged, key=lambda x: x["disparity"], reverse=True)[:10]:
            rates = " / ".join(f"{k}: {v:.0%}" for k, v in f["pass_rates"].items())
            print(f"  {f['company_name']:35s} {f['tier']:8s} "
                  f"{f['disparity']:9.3f}  {f['p_value']:9.5f}  {f['top_bias_criterion']}")
            print(f"    → Pass rates: {rates}")
    else:
        print("  No companies flagged — criteria appear demographically neutral.")

    print("\n" + "=" * 60)
    print("  Research Claim (for paper):")
    print("  ─────────────────────────────")
    pct = summary['flag_rate'] * 100
    print(f"  {pct:.0f}% of companies in the pool have placement criteria that")
    print("  produce statistically significant gender-based disparate impact")
    print("  (Fisher's exact test, p < 0.05, disparity > 10%).")
    print("  This demonstrates that upstream bias in criteria design is a")
    print("  measurable and detectable problem — independent of any ML model.")
    print("=" * 60)


def main():
    print("\n" + "=" * 60)
    print("  OPTION 3 — Criteria Bias Detection Pipeline")
    print("=" * 60)

    # Step 1 & 2: Detect + report
    print("\n── STEP 1: Run Statistical Bias Tests ───────────────────────")
    report = run_criteria_bias_detection()

    # Step 3: IEEE summary
    print("\n── STEP 2: IEEE Summary ─────────────────────────────────────")
    print_ieee_summary(report)

    # Load metrics for quick verification
    prefix = "resume_realworld_" if dataset_variant() == "realworld" else ""
    csv_path = os.path.join(MODEL_DIR, f"{prefix}criteria_bias_report.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        print(f"\n📊  Disparity distribution across all companies:")
        print(f"   Mean gender disparity : {df['gender_disparity'].mean():.4f}")
        print(f"   Max  gender disparity : {df['gender_disparity'].max():.4f}")
        print(f"   Median gender disparity: {df['gender_disparity'].median():.4f}")
        print(f"   Tier-1 avg disparity  : "
              f"{df[df['tier']=='Tier1']['gender_disparity'].mean():.4f}")
        print(f"   Tier-2 avg disparity  : "
              f"{df[df['tier']=='Tier2']['gender_disparity'].mean():.4f}")
        print(f"   Tier-3 avg disparity  : "
              f"{df[df['tier']=='Tier3']['gender_disparity'].mean():.4f}")

    print("\n" + "=" * 60)
    print("  ✅  Option 3 Complete — artifacts in backend/models/")
    print("=" * 60)


if __name__ == "__main__":
    main()
