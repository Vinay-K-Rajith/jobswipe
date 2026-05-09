"""
Fairness Audit: Check for demographic bias in model predictions.
Runs demographic parity and equalized odds checks across gender/department groups.

Extended (Option 3): also runs upstream criteria bias detection to flag
companies whose hard rules produce statistically significant disparate impact.
"""

import pandas as pd
import numpy as np
import pickle
import os
import json

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')


def load_model_and_data():
    """Load trained model, scaler, and data for auditing."""
    with open(os.path.join(MODEL_DIR, "model.pkl"), "rb") as f:
        model = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "rb") as f:
        scaler = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "feature_columns.json"), "r") as f:
        feature_cols = json.load(f)

    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))
    pairs = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))
    labels = pd.read_csv(os.path.join(DATA_DIR, "training_labels.csv"))

    return model, scaler, feature_cols, students, pairs, labels


def demographic_parity(predictions_df, group_col, outcome_col="predicted"):
    """
    Check Demographic Parity: P(Y=1 | G=g) should be similar for all g.
    Returns per-group rates and the max disparity.
    """
    rates = predictions_df.groupby(group_col)[outcome_col].mean()
    max_rate = rates.max()
    min_rate = rates.min()
    disparity = max_rate - min_rate

    return {
        "group_rates": rates.to_dict(),
        "max_rate": float(max_rate),
        "min_rate": float(min_rate),
        "disparity": float(disparity),
        "fair": disparity < 0.10,  # 10% threshold
    }


def equalized_odds(predictions_df, group_col, outcome_col="predicted", label_col="actual"):
    """
    Check Equalized Odds: TPR and FPR should be similar across groups.
    """
    results = {}
    for group_val in predictions_df[group_col].unique():
        group_data = predictions_df[predictions_df[group_col] == group_val]

        positives = group_data[group_data[label_col] == 1]
        negatives = group_data[group_data[label_col] == 0]

        tpr = positives[outcome_col].mean() if len(positives) > 0 else 0
        fpr = negatives[outcome_col].mean() if len(negatives) > 0 else 0

        results[str(group_val)] = {"tpr": float(tpr), "fpr": float(fpr)}

    tprs = [v["tpr"] for v in results.values()]
    fprs = [v["fpr"] for v in results.values()]

    return {
        "group_metrics": results,
        "tpr_disparity": float(max(tprs) - min(tprs)) if tprs else 0,
        "fpr_disparity": float(max(fprs) - min(fprs)) if fprs else 0,
        "fair": (max(tprs) - min(tprs) < 0.10 and max(fprs) - min(fprs) < 0.10) if tprs and fprs else True,
    }


def run_fairness_audit():
    """Run full fairness audit and generate report."""
    print("=" * 60)
    print("  🛡️  Fairness Audit Report")
    print("=" * 60)

    model, scaler, feature_cols, students, pairs, labels = load_model_and_data()

    # Get model predictions on all data
    X = pairs[feature_cols].fillna(0)
    X_scaled = scaler.transform(X)
    predictions = model.predict(X_scaled)
    probabilities = model.predict_proba(X_scaled)[:, 1]

    # Build audit DataFrame
    audit_df = pairs[["student_id", "company_id"]].copy()
    audit_df["predicted"] = predictions
    audit_df["probability"] = probabilities

    # Merge actual labels
    audit_df = audit_df.merge(
        labels[["student_id", "company_id", "eligible"]],
        on=["student_id", "company_id"]
    )
    audit_df.rename(columns={"eligible": "actual"}, inplace=True)

    # Merge student demographics (for audit, NOT used in model)
    audit_df = audit_df.merge(
        students[["student_id", "gender", "department", "10th_board", "12th_board"]],
        on="student_id"
    )

    report = {}

    # === GENDER PARITY ===
    print("\n📊 1. GENDER DEMOGRAPHIC PARITY")
    print("-" * 40)
    gender_parity = demographic_parity(audit_df, "gender")
    for group, rate in gender_parity["group_rates"].items():
        print(f"  {group:15s}: {rate:.4f} ({rate*100:.1f}% predicted eligible)")
    print(f"  Disparity: {gender_parity['disparity']:.4f}")
    print(f"  Fair (< 10% gap): {'✅ YES' if gender_parity['fair'] else '⚠️  NO'}")
    report["gender_parity"] = gender_parity

    # === GENDER EQUALIZED ODDS ===
    print("\n📊 2. GENDER EQUALIZED ODDS")
    print("-" * 40)
    gender_eq = equalized_odds(audit_df, "gender")
    for group, metrics in gender_eq["group_metrics"].items():
        print(f"  {group:15s}: TPR={metrics['tpr']:.4f}, FPR={metrics['fpr']:.4f}")
    print(f"  TPR Disparity: {gender_eq['tpr_disparity']:.4f}")
    print(f"  FPR Disparity: {gender_eq['fpr_disparity']:.4f}")
    print(f"  Fair: {'✅ YES' if gender_eq['fair'] else '⚠️  NO'}")
    report["gender_equalized_odds"] = gender_eq

    # === DEPARTMENT PARITY ===
    print("\n📊 3. DEPARTMENT DEMOGRAPHIC PARITY")
    print("-" * 40)
    dept_parity = demographic_parity(audit_df, "department")
    for group, rate in sorted(dept_parity["group_rates"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {group:15s}: {rate:.4f} ({rate*100:.1f}%)")
    print(f"  Disparity: {dept_parity['disparity']:.4f}")
    print(f"  Fair (< 10% gap): {'✅ YES' if dept_parity['fair'] else '⚠️  NO — review needed'}")
    report["department_parity"] = dept_parity

    # === BOARD TYPE PARITY (should NOT affect outcomes) ===
    print("\n📊 4. 10TH BOARD DEMOGRAPHIC PARITY")
    print("-" * 40)
    board10_parity = demographic_parity(audit_df, "10th_board")
    for group, rate in board10_parity["group_rates"].items():
        print(f"  {group:15s}: {rate:.4f} ({rate*100:.1f}%)")
    print(f"  Disparity: {board10_parity['disparity']:.4f}")
    print(f"  Fair (< 10% gap): {'✅ YES' if board10_parity['fair'] else '⚠️  NO — board bias detected!'}")
    report["board_10th_parity"] = board10_parity

    print("\n📊 5. 12TH BOARD DEMOGRAPHIC PARITY")
    print("-" * 40)
    board12_parity = demographic_parity(audit_df, "12th_board")
    for group, rate in board12_parity["group_rates"].items():
        print(f"  {group:15s}: {rate:.4f} ({rate*100:.1f}%)")
    print(f"  Disparity: {board12_parity['disparity']:.4f}")
    print(f"  Fair (< 10% gap): {'✅ YES' if board12_parity['fair'] else '⚠️  NO — board bias detected!'}")
    report["board_12th_parity"] = board12_parity

    # Overall verdict
    print("\n" + "=" * 60)
    all_fair = all([
        gender_parity["fair"],
        gender_eq["fair"],
        dept_parity["fair"],
        board10_parity["fair"],
        board12_parity["fair"],
    ])
    if all_fair:
        print("  ✅ OVERALL: Model passes all fairness checks!")
    else:
        print("  ⚠️  OVERALL: Some fairness checks failed — review recommended")
        if not gender_parity["fair"]:
            print("    → Gender parity gap exceeds 10%")
        if not gender_eq["fair"]:
            print("    → Gender equalized odds gap exceeds 10%")
        if not dept_parity["fair"]:
            print("    Department parity gap exceeds 10%")
        if not board10_parity["fair"]:
            print("    → 10th board shows bias (should be neutral)")
        if not board12_parity["fair"]:
            print("    → 12th board shows bias (should be neutral)")
    print("=" * 60)

    # Save report
    report_path = os.path.join(MODEL_DIR, "fairness_report.json")

    # Deep-convert numpy types for JSON serialization
    def sanitize(obj):
        if isinstance(obj, dict):
            return {str(k): sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize(v) for v in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    report_clean = sanitize(report)
    with open(report_path, "w") as f:
        json.dump(report_clean, f, indent=2)
    print(f"\n💾 Fairness report saved → {report_path}")

    return report


def upstream_criteria_audit() -> dict:
    """
    Option 3 integration: run criteria-level bias detection and return summary.
    Flags companies whose hard placement rules produce statistically significant
    gender disparate impact (Fisher's Exact Test, p < 0.05, disparity > 10%).
    """
    try:
        from src.model.criteria_bias_detector import run_criteria_bias_detection
        print("\n" + "=" * 60)
        print("  🔬  Upstream Criteria Bias Audit (Option 3)")
        print("=" * 60)
        report = run_criteria_bias_detection()
        n_flagged = report["summary"]["n_flagged"]
        n_total   = report["summary"]["n_companies"]
        print(f"\n  Summary: {n_flagged}/{n_total} companies have biased criteria ")
        print(f"  (p < 0.05, disparity > 10%)")
        return report
    except ImportError:
        print("⚠️  criteria_bias_detector not found — skipping upstream audit")
        return {}


if __name__ == "__main__":
    run_fairness_audit()
    upstream_criteria_audit()
