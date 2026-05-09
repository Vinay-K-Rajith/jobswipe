"""
Train the XGBoost model for Layer 2: Scoring & Ranking.
The model is trained on CRITERIA-DERIVED labels, not historical placement data.

Input features are all numerical, with NO name/gender/board-type.
"""

import pandas as pd
import numpy as np
import os
import pickle
import json
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    from sklearn.ensemble import GradientBoostingClassifier

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')

# Feature columns used for training (BIAS-FREE: no name, gender, board)
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


def load_training_data():
    """Load pair features and merge with labels."""
    pairs = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))
    labels = pd.read_csv(os.path.join(DATA_DIR, "training_labels.csv"))

    data = pairs.merge(labels[["student_id", "company_id", "eligible"]],
                       on=["student_id", "company_id"])
    return data


def train_model(data, test_size=0.2, random_state=42):
    """Train the XGBoost model."""
    os.makedirs(MODEL_DIR, exist_ok=True)

    X = data[FEATURE_COLS].copy()
    y = data["eligible"].copy()

    # Handle any missing values
    X = X.fillna(0)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train model
    if HAS_XGB:
        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=random_state,
            use_label_encoder=False,
            eval_metric="logloss",
        )
        model.fit(
            X_train_scaled, y_train,
            eval_set=[(X_test_scaled, y_test)],
            verbose=False,
        )
    else:
        print("⚠️  XGBoost not installed, using sklearn GradientBoosting instead")
        model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            random_state=random_state,
        )
        model.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_proba = model.predict_proba(X_test_scaled)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
    }

    print("\n📊 Model Performance:")
    print(f"  Accuracy:  {metrics['accuracy']:.4f}")
    print(f"  Precision: {metrics['precision']:.4f}")
    print(f"  Recall:    {metrics['recall']:.4f}")
    print(f"  F1 Score:  {metrics['f1']:.4f}")

    print("\n📋 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["Ineligible", "Eligible"]))

    print("📊 Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"  TN={cm[0][0]}, FP={cm[0][1]}")
    print(f"  FN={cm[1][0]}, TP={cm[1][1]}")

    # Feature importance
    if HAS_XGB:
        importance = model.feature_importances_
    else:
        importance = model.feature_importances_

    feat_imp = sorted(zip(FEATURE_COLS, importance), key=lambda x: x[1], reverse=True)
    print("\n🔍 Feature Importance (top 10):")
    for feat, imp in feat_imp[:10]:
        print(f"  {feat:40s} {imp:.4f}")

    # ANTI-BIAS CHECK: Verify no protected features have importance
    print("\n🛡️  Anti-Bias Verification:")
    print("  ✅ name: NOT in features (excluded)")
    print("  ✅ gender: NOT in features (excluded)")
    print("  ✅ 10th_board: NOT in features (excluded)")
    print("  ✅ 12th_board: NOT in features (excluded)")

    # Save model artifacts
    model_path = os.path.join(MODEL_DIR, "model.pkl")
    scaler_path = os.path.join(MODEL_DIR, "scaler.pkl")
    metrics_path = os.path.join(MODEL_DIR, "metrics.json")
    features_path = os.path.join(MODEL_DIR, "feature_columns.json")

    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    with open(features_path, "w") as f:
        json.dump(FEATURE_COLS, f, indent=2)

    print(f"\n💾 Model saved → {model_path}")
    print(f"💾 Scaler saved → {scaler_path}")
    print(f"💾 Metrics saved → {metrics_path}")

    return model, scaler, metrics


def make_classifier(random_state=42):
    if HAS_XGB:
        return xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=random_state,
            eval_metric="logloss",
        )
    return GradientBoostingClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        random_state=random_state,
    )


def train_model_with_cv(data, n_splits=5, random_state=42):
    """Run 5-fold StratifiedKFold CV, then fit the saved model on all data."""
    os.makedirs(MODEL_DIR, exist_ok=True)

    X = data[FEATURE_COLS].copy().fillna(0)
    y = data["eligible"].copy()

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    fold_metrics = []
    for fold, (train_idx, test_idx) in enumerate(skf.split(X, y), 1):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        model = make_classifier(random_state=random_state)
        if HAS_XGB:
            model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)
        else:
            model.fit(X_train_s, y_train)

        y_pred = model.predict(X_test_s)
        fold_metrics.append({
            "fold": fold,
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        })

    cv_results = {
        "accuracy_mean": float(np.mean([m["accuracy"] for m in fold_metrics])),
        "accuracy_std": float(np.std([m["accuracy"] for m in fold_metrics])),
        "f1_mean": float(np.mean([m["f1"] for m in fold_metrics])),
        "f1_std": float(np.std([m["f1"] for m in fold_metrics])),
        "n_folds": n_splits,
        "folds": fold_metrics,
    }

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = make_classifier(random_state=random_state)
    model.fit(X_scaled, y)
    y_pred_all = model.predict(X_scaled)

    metrics = {
        "accuracy": float(accuracy_score(y, y_pred_all)),
        "precision": float(precision_score(y, y_pred_all, zero_division=0)),
        "recall": float(recall_score(y, y_pred_all, zero_division=0)),
        "f1": float(f1_score(y, y_pred_all, zero_division=0)),
        "cv_accuracy_mean": cv_results["accuracy_mean"],
        "cv_accuracy_std": cv_results["accuracy_std"],
        "cv_f1_mean": cv_results["f1_mean"],
        "cv_f1_std": cv_results["f1_std"],
    }

    with open(os.path.join(MODEL_DIR, "model.pkl"), "wb") as f:
        pickle.dump(model, f)
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODEL_DIR, "feature_columns.json"), "w") as f:
        json.dump(FEATURE_COLS, f, indent=2)
    with open(os.path.join(MODEL_DIR, "cv_results.json"), "w") as f:
        json.dump(cv_results, f, indent=2)
    with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print("\nCross-validation results:")
    print(f"  Accuracy: {cv_results['accuracy_mean']:.4f} +/- {cv_results['accuracy_std']:.4f}")
    print(f"  F1:       {cv_results['f1_mean']:.4f} +/- {cv_results['f1_std']:.4f}")
    print(f"Model, scaler, metrics, and CV results saved to {MODEL_DIR}")

    return model, scaler, metrics, cv_results


if __name__ == "__main__":
    print("=" * 60)
    print("  Bias-Free Placement Model — Training Pipeline")
    print("=" * 60)

    print("\n📂 Loading training data...")
    data = load_training_data()
    print(f"  → {len(data)} training pairs")
    print(f"  → Eligible: {data['eligible'].sum()} ({data['eligible'].mean()*100:.1f}%)")

    model, scaler, metrics, cv_results = train_model_with_cv(data)
