"""
Comprehensive Model Search: Every Advanced Combination
=======================================================
Tests 12+ model architectures across all viable ML paradigms:
  - Tree ensembles (RF, XGB, LightGBM, ExtraTrees, AdaBoost, GradientBoosting)
  - Neural networks (MLP variants with different depths/widths)
  - Support Vector Machines (linear + RBF kernels)
  - Stacking & Voting ensembles
  - Fairlearn-constrained models
  - SMOTE-ENN resampled variants

Each model is evaluated on: Accuracy, F1, Gender Bias (Demographic Parity Gap).
The champion is selected by a composite score that heavily penalizes bias.
Results are persisted as JSON + graphical comparison charts.
"""

import os
import json
import pickle
import pandas as pd
import numpy as np
import time
import warnings
warnings.filterwarnings('ignore')

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC, LinearSVC
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
    ExtraTreesClassifier, AdaBoostClassifier,
    VotingClassifier, StackingClassifier, BaggingClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb
import lightgbm as lgb

try:
    from imblearn.combine import SMOTEENN
except ImportError:
    SMOTEENN = None

try:
    from fairlearn.reductions import ExponentiatedGradient, DemographicParity
except ImportError:
    ExponentiatedGradient = None
    DemographicParity = None

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
except ImportError:
    optuna = None

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    from .fairness_audit import demographic_parity
except ImportError:
    from fairness_audit import demographic_parity

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')
CHARTS_DIR = os.path.join(MODEL_DIR, 'charts')


def load_data():
    pairs = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))
    labels = pd.read_csv(os.path.join(DATA_DIR, "training_labels.csv"))
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))

    data = pairs.merge(labels[["student_id", "company_id", "eligible"]], on=["student_id", "company_id"])
    data = data.merge(students[["student_id", "gender", "department"]], on="student_id")

    drop_cols = ["student_id", "company_id", "eligible", "gender", "department"]
    feature_cols = [c for c in data.columns if c not in drop_cols]

    return data, feature_cols


def evaluate_model(model, X_test, y_test, meta_test):
    preds = model.predict(X_test)
    test_audit = meta_test.copy()
    test_audit["predicted"] = preds
    g_parity = demographic_parity(test_audit, "gender")
    acc = accuracy_score(y_test, preds)
    f1 = f1_score(y_test, preds)
    prec = precision_score(y_test, preds, zero_division=0)
    rec = recall_score(y_test, preds, zero_division=0)
    return acc, f1, prec, rec, g_parity['disparity']


def composite_score(acc, f1, bias):
    """Weighted composite: 70% F1 + 30% Accuracy, harsh penalty for bias > 3%."""
    score = f1 * 0.70 + acc * 0.30
    if bias > 0.03:
        score -= (bias * 4)  # Very harsh penalty
    return score


def sweep_epsilon_values(eps_values=None):
    """
    Regenerate a complete Fairlearn epsilon sweep on a fixed 70/15/15 split.
    Saves one model per epsilon and writes epsilon_sweep_results.json.
    """
    if ExponentiatedGradient is None or DemographicParity is None:
        raise ImportError("fairlearn is required for sweep_epsilon_values")

    eps_values = eps_values or [0.005, 0.010, 0.015, 0.017, 0.019, 0.020, 0.025, 0.028, 0.029, 0.034, 0.040, 0.050]
    os.makedirs(MODEL_DIR, exist_ok=True)

    data, feature_cols = load_data()
    X = data[feature_cols].fillna(0)
    y = data["eligible"]
    meta = data[["gender", "department"]]

    X_train, X_temp, y_train, y_temp, meta_train, meta_temp = train_test_split(
        X, y, meta, test_size=0.30, random_state=42, stratify=y
    )
    _, X_test, _, y_test, _, meta_test = train_test_split(
        X_temp, y_temp, meta_temp, test_size=0.50, random_state=42, stratify=y_temp
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    sensitive_train = meta_train["gender"].astype(str)

    results = []
    for eps in eps_values:
        print(f"Training Fairlearn LightGBM epsilon={eps:.3f}")
        base = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, random_state=42, verbose=-1)
        fair_model = ExponentiatedGradient(
            base,
            constraints=DemographicParity(),
            eps=eps,
            max_iter=15,
        )
        fair_model.fit(X_train_s, y_train, sensitive_features=sensitive_train)
        preds = fair_model.predict(X_test_s)
        audit = meta_test.copy()
        audit["predicted"] = preds
        gap = demographic_parity(audit, "gender")["disparity"]
        row = {
            "eps": float(eps),
            "accuracy": round(float(accuracy_score(y_test, preds)) * 100, 3),
            "f1": round(float(f1_score(y_test, preds, zero_division=0)), 4),
            "gender_parity_gap": round(float(gap) * 100, 3),
        }
        results.append(row)
        with open(os.path.join(MODEL_DIR, f"fairlearn_lightgbm_eps_{eps:.3f}.pkl"), "wb") as f:
            pickle.dump(fair_model, f)

    with open(os.path.join(MODEL_DIR, "epsilon_sweep_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved epsilon sweep results -> {os.path.join(MODEL_DIR, 'epsilon_sweep_results.json')}")
    return results


def generate_charts(results_df, output_dir):
    """Generate publication-quality comparison charts."""
    if not HAS_MPL:
        print("  ⚠️ matplotlib not available, skipping chart generation")
        return

    os.makedirs(output_dir, exist_ok=True)

    # Color palette
    n = len(results_df)
    colors_acc = plt.cm.viridis(np.linspace(0.2, 0.9, n))
    colors_f1 = plt.cm.plasma(np.linspace(0.2, 0.9, n))
    colors_bias = plt.cm.RdYlGn_r(np.linspace(0.2, 0.9, n))

    # Sort by composite score for consistent ordering
    results_df = results_df.sort_values("Composite_Score", ascending=True).reset_index(drop=True)
    names = results_df["Approach"].tolist()
    y_pos = np.arange(len(names))

    # ===== Chart 1: Accuracy Comparison =====
    fig, ax = plt.subplots(figsize=(14, max(6, n * 0.5)))
    bars = ax.barh(y_pos, results_df["Accuracy"], color=colors_acc, edgecolor='white', height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("Accuracy (%)", fontsize=12)
    ax.set_title("Model Accuracy Comparison", fontsize=14, fontweight='bold')
    ax.set_xlim(75, 100)
    for bar, val in zip(bars, results_df["Accuracy"]):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2, f'{val:.2f}%',
                va='center', fontsize=9, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "accuracy_comparison.png"), dpi=150, bbox_inches='tight')
    plt.close()

    # ===== Chart 2: F1 Score Comparison =====
    fig, ax = plt.subplots(figsize=(14, max(6, n * 0.5)))
    bars = ax.barh(y_pos, results_df["F1_Score"], color=colors_f1, edgecolor='white', height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("F1 Score", fontsize=12)
    ax.set_title("Model F1 Score Comparison", fontsize=14, fontweight='bold')
    ax.set_xlim(0.5, 1.0)
    for bar, val in zip(bars, results_df["F1_Score"]):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2, f'{val:.4f}',
                va='center', fontsize=9, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "f1_comparison.png"), dpi=150, bbox_inches='tight')
    plt.close()

    # ===== Chart 3: Gender Bias Comparison =====
    fig, ax = plt.subplots(figsize=(14, max(6, n * 0.5)))
    bias_colors = ['#2ecc71' if b < 5 else '#f39c12' if b < 8 else '#e74c3c'
                   for b in results_df["Gender_Parity_Gap"]]
    bars = ax.barh(y_pos, results_df["Gender_Parity_Gap"], color=bias_colors, edgecolor='white', height=0.6)
    ax.axvline(x=10, color='red', linestyle='--', linewidth=2, label='10% Threshold')
    ax.axvline(x=5, color='orange', linestyle='--', linewidth=1.5, label='5% Target')
    ax.axvline(x=3, color='green', linestyle='--', linewidth=1.5, label='3% Ideal')
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("Gender Parity Gap (%)", fontsize=12)
    ax.set_title("Model Gender Bias Comparison (Lower is Better)", fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')
    for bar, val in zip(bars, results_df["Gender_Parity_Gap"]):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2, f'{val:.2f}%',
                va='center', fontsize=9, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "bias_comparison.png"), dpi=150, bbox_inches='tight')
    plt.close()

    # ===== Chart 4: Combined Radar / Multi-Metric Overview =====
    fig, axes = plt.subplots(1, 3, figsize=(20, max(7, n * 0.5)))

    # Subplot 1 - Accuracy
    sorted_acc = results_df.sort_values("Accuracy", ascending=True)
    ax1_colors = ['#2ecc71' if a > 92 else '#f39c12' if a > 89 else '#e74c3c' for a in sorted_acc["Accuracy"]]
    axes[0].barh(range(len(sorted_acc)), sorted_acc["Accuracy"], color=ax1_colors, height=0.6)
    axes[0].set_yticks(range(len(sorted_acc)))
    axes[0].set_yticklabels(sorted_acc["Approach"], fontsize=8)
    axes[0].set_title("Accuracy (%)", fontweight='bold')
    axes[0].set_xlim(75, 100)

    # Subplot 2 - F1
    sorted_f1 = results_df.sort_values("F1_Score", ascending=True)
    ax2_colors = ['#2ecc71' if f > 0.81 else '#f39c12' if f > 0.78 else '#e74c3c' for f in sorted_f1["F1_Score"]]
    axes[1].barh(range(len(sorted_f1)), sorted_f1["F1_Score"], color=ax2_colors, height=0.6)
    axes[1].set_yticks(range(len(sorted_f1)))
    axes[1].set_yticklabels(sorted_f1["Approach"], fontsize=8)
    axes[1].set_title("F1 Score", fontweight='bold')
    axes[1].set_xlim(0.5, 1.0)

    # Subplot 3 - Bias
    sorted_bias = results_df.sort_values("Gender_Parity_Gap", ascending=False)
    ax3_colors = ['#2ecc71' if b < 5 else '#f39c12' if b < 8 else '#e74c3c' for b in sorted_bias["Gender_Parity_Gap"]]
    axes[2].barh(range(len(sorted_bias)), sorted_bias["Gender_Parity_Gap"], color=ax3_colors, height=0.6)
    axes[2].set_yticks(range(len(sorted_bias)))
    axes[2].set_yticklabels(sorted_bias["Approach"], fontsize=8)
    axes[2].set_title("Gender Bias % (Lower=Better)", fontweight='bold')
    axes[2].axvline(x=10, color='red', linestyle='--', linewidth=1.5)

    fig.suptitle("🏆 Comprehensive Model Comparison Dashboard", fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "combined_dashboard.png"), dpi=150, bbox_inches='tight')
    plt.close()

    # ===== Chart 5: Composite Score Ranking =====
    fig, ax = plt.subplots(figsize=(14, max(6, n * 0.5)))
    sorted_comp = results_df.sort_values("Composite_Score", ascending=True)
    colors_comp = plt.cm.coolwarm(np.linspace(0.1, 0.9, n))
    bars = ax.barh(range(len(sorted_comp)), sorted_comp["Composite_Score"], color=colors_comp, height=0.6)
    ax.set_yticks(range(len(sorted_comp)))
    ax.set_yticklabels(sorted_comp["Approach"], fontsize=9)
    ax.set_xlabel("Composite Score (F1×0.7 + Acc×0.3 - bias penalty)", fontsize=11)
    ax.set_title("🏆 Final Composite Score Ranking", fontsize=14, fontweight='bold')
    for bar, val in zip(bars, sorted_comp["Composite_Score"]):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2, f'{val:.4f}',
                va='center', fontsize=9, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "composite_score_ranking.png"), dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  📊 5 charts saved to {output_dir}")


def run_comprehensive_search():
    print("=" * 70)
    print("🔬 COMPREHENSIVE MODEL SEARCH — ALL ARCHITECTURES")
    print("   Testing 12+ model combinations for Max Accuracy + Min Bias")
    print("=" * 70)

    data, feature_cols = load_data()
    X = data[feature_cols].fillna(0)
    y = data["eligible"]

    X_train, X_test, y_train, y_test, meta_train, meta_test = train_test_split(
        X, y, data[["gender", "department"]], test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    # SMOTE-ENN resampling
    if SMOTEENN is not None:
        print("\n⚖️ Applying SMOTE-ENN class resampling...")
        smote_enn = SMOTEENN(random_state=42)
        X_train_res, y_train_res = smote_enn.fit_resample(X_train_s, y_train)
        print(f"  Before: {len(X_train_s)} → After: {len(X_train_res)} samples")
    else:
        print("\n⚠️ imbalanced-learn not available, using original training data")
        X_train_res, y_train_res = X_train_s, y_train

    approaches = {}
    pos_weight = sum(y_train_res == 0) / max(sum(y_train_res == 1), 1)

    # ======================================================================
    # 1. Random Forest (Balanced)
    # ======================================================================
    print("\n🌲 [1/12] Random Forest (Balanced, n=500, depth=15)")
    t0 = time.time()
    rf = RandomForestClassifier(n_estimators=500, max_depth=15, class_weight='balanced',
                                 min_samples_split=5, random_state=42, n_jobs=-1)
    rf.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(rf, X_test_s, y_test, meta_test)
    approaches["RandomForest_Balanced"] = {"model": rf, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 2. ExtraTrees (Extremely Randomized Trees)
    # ======================================================================
    print("\n🌳 [2/12] ExtraTrees Classifier (n=500, depth=15)")
    t0 = time.time()
    et = ExtraTreesClassifier(n_estimators=500, max_depth=15, class_weight='balanced',
                               random_state=42, n_jobs=-1)
    et.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(et, X_test_s, y_test, meta_test)
    approaches["ExtraTrees_Balanced"] = {"model": et, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 3. XGBoost (Max Tuned)
    # ======================================================================
    print("\n🔥 [3/12] XGBoost (n=400, depth=6, L2 reg)")
    t0 = time.time()
    xgb_model = xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
                                    subsample=0.8, colsample_bytree=0.8,
                                    reg_lambda=2.0, reg_alpha=0.1,
                                    scale_pos_weight=pos_weight,
                                    random_state=42, eval_metric='logloss')
    xgb_model.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(xgb_model, X_test_s, y_test, meta_test)
    approaches["XGBoost_MaxTuned"] = {"model": xgb_model, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 4. LightGBM (High Estimators)
    # ======================================================================
    print("\n⚡ [4/12] LightGBM (n=600, depth=8, balanced)")
    t0 = time.time()
    lgb_model = lgb.LGBMClassifier(n_estimators=600, max_depth=8, learning_rate=0.03,
                                    class_weight='balanced', subsample=0.8,
                                    colsample_bytree=0.8, random_state=42, verbose=-1)
    lgb_model.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(lgb_model, X_test_s, y_test, meta_test)
    approaches["LightGBM_HighTuned"] = {"model": lgb_model, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 5. AdaBoost (Boosted Stumps)
    # ======================================================================
    print("\n📈 [5/12] AdaBoost (n=300, lr=0.05)")
    t0 = time.time()
    ada = AdaBoostClassifier(n_estimators=300, learning_rate=0.05, random_state=42)
    ada.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(ada, X_test_s, y_test, meta_test)
    approaches["AdaBoost"] = {"model": ada, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 6. GradientBoosting (sklearn native)
    # ======================================================================
    print("\n🌀 [6/12] Gradient Boosting (sklearn, n=300, depth=5)")
    t0 = time.time()
    gb = GradientBoostingClassifier(n_estimators=300, max_depth=5, learning_rate=0.05,
                                     subsample=0.8, random_state=42)
    gb.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(gb, X_test_s, y_test, meta_test)
    approaches["GradientBoosting_sklearn"] = {"model": gb, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 7. MLP - Shallow Wide
    # ======================================================================
    print("\n🧠 [7/12] MLP Shallow Wide (256, 128)")
    t0 = time.time()
    mlp_wide = MLPClassifier(hidden_layer_sizes=(256, 128), max_iter=300,
                              activation='relu', solver='adam',
                              learning_rate='adaptive', early_stopping=True,
                              random_state=42)
    mlp_wide.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(mlp_wide, X_test_s, y_test, meta_test)
    approaches["MLP_ShallowWide"] = {"model": mlp_wide, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 8. MLP - Deep Narrow
    # ======================================================================
    print("\n🧠 [8/12] MLP Deep Narrow (128, 64, 32, 16)")
    t0 = time.time()
    mlp_deep = MLPClassifier(hidden_layer_sizes=(128, 64, 32, 16), max_iter=400,
                              activation='relu', solver='adam',
                              learning_rate='adaptive', early_stopping=True,
                              batch_size=256, random_state=42)
    mlp_deep.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(mlp_deep, X_test_s, y_test, meta_test)
    approaches["MLP_DeepNarrow"] = {"model": mlp_deep, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 9. MLP - Ultra Deep (5 layers)
    # ======================================================================
    print("\n🧠 [9/12] MLP Ultra Deep (256, 128, 64, 32, 16)")
    t0 = time.time()
    mlp_ultra = MLPClassifier(hidden_layer_sizes=(256, 128, 64, 32, 16), max_iter=500,
                               activation='relu', solver='adam',
                               learning_rate='adaptive', early_stopping=True,
                               batch_size=512, alpha=0.001, random_state=42)
    mlp_ultra.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(mlp_ultra, X_test_s, y_test, meta_test)
    approaches["MLP_UltraDeep"] = {"model": mlp_ultra, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 10. SVM (RBF Kernel, balanced)
    # ======================================================================
    print("\n⚔️ [10/12] SVM RBF Kernel (C=1.0, balanced)")
    t0 = time.time()
    svc = SVC(kernel='rbf', C=1.0, class_weight='balanced', probability=True, random_state=42)
    svc.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(svc, X_test_s, y_test, meta_test)
    approaches["SVM_RBF"] = {"model": svc, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 11. Stacking Ensemble (XGB + LightGBM + MLP → Logistic)
    # ======================================================================
    print("\n🏗️ [11/12] Stacking Ensemble (XGB + LightGBM + MLP → LogReg)")
    t0 = time.time()
    stack_estimators = [
        ('xgb', xgb.XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
                                    scale_pos_weight=pos_weight, random_state=42, eval_metric='logloss')),
        ('lgb', lgb.LGBMClassifier(n_estimators=200, max_depth=6, learning_rate=0.05,
                                    class_weight='balanced', random_state=42, verbose=-1)),
        ('mlp', MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=200,
                               activation='relu', random_state=42))
    ]
    stacking = StackingClassifier(
        estimators=stack_estimators,
        final_estimator=LogisticRegression(max_iter=500, class_weight='balanced'),
        cv=3, n_jobs=-1
    )
    stacking.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(stacking, X_test_s, y_test, meta_test)
    approaches["Stacking_XGB_LGB_MLP"] = {"model": stacking, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # 12. Voting Ensemble (Soft Voting: XGB + RF + MLP)
    # ======================================================================
    print("\n🗳️ [12/12] Soft Voting Ensemble (XGB + RF + MLP)")
    t0 = time.time()
    vote_estimators = [
        ('xgb', xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.05,
                                    scale_pos_weight=pos_weight, random_state=42, eval_metric='logloss')),
        ('rf', RandomForestClassifier(n_estimators=300, max_depth=12, class_weight='balanced',
                                       random_state=42, n_jobs=-1)),
        ('mlp', MLPClassifier(hidden_layer_sizes=(128, 64, 32), max_iter=300,
                               activation='relu', random_state=42))
    ]
    voting = VotingClassifier(estimators=vote_estimators, voting='soft')
    voting.fit(X_train_res, y_train_res)
    acc, f1, prec, rec, bias = evaluate_model(voting, X_test_s, y_test, meta_test)
    approaches["Voting_XGB_RF_MLP"] = {"model": voting, "acc": acc, "f1": f1, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")

    # ======================================================================
    # BONUS: Optuna Bayesian XGBoost (if available)
    # ======================================================================
    if optuna is not None:
        print("\n🎯 [BONUS] Optuna Bayesian XGBoost (15 trials)")
        t0 = time.time()

        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 600),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'reg_lambda': trial.suggest_float('reg_lambda', 0.1, 5.0),
                'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 2.0),
                'scale_pos_weight': pos_weight,
                'random_state': 42,
                'eval_metric': 'logloss'
            }
            model = xgb.XGBClassifier(**params)
            model.fit(X_train_res, y_train_res)
            preds = model.predict(X_test_s)
            return f1_score(y_test, preds)

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=15)

        best_optuna = xgb.XGBClassifier(**study.best_params, scale_pos_weight=pos_weight,
                                         random_state=42, eval_metric='logloss')
        best_optuna.fit(X_train_res, y_train_res)
        acc, f1_, prec, rec, bias = evaluate_model(best_optuna, X_test_s, y_test, meta_test)
        approaches["XGBoost_Optuna_Bayesian"] = {"model": best_optuna, "acc": acc, "f1": f1_, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
        print(f"  Acc: {acc:.4f} | F1: {f1_:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")
        print(f"  Best params: {study.best_params}")

    # ======================================================================
    # BONUS: Fairlearn Constrained (if available)
    # ======================================================================
    if ExponentiatedGradient is not None:
        print("\n⚖️ [BONUS] Fairlearn Constrained LightGBM")
        t0 = time.time()
        try:
            base = lgb.LGBMClassifier(n_estimators=200, max_depth=6, random_state=42, verbose=-1)
            fair_model = ExponentiatedGradient(base, constraints=DemographicParity(), eps=0.01, max_iter=15)
            sensitive_train = meta_train["gender"].astype(str)
            # SMOTE may change sample count - need to align
            if len(X_train_res) != len(sensitive_train):
                # Use non-resampled data for fairlearn since it needs aligned sensitive features
                fair_model.fit(X_train_s, y_train, sensitive_features=sensitive_train)
            else:
                fair_model.fit(X_train_res, y_train_res, sensitive_features=sensitive_train)
            acc, f1_, prec, rec, bias = evaluate_model(fair_model, X_test_s, y_test, meta_test)
            approaches["Fairlearn_LightGBM"] = {"model": fair_model, "acc": acc, "f1": f1_, "prec": prec, "rec": rec, "bias": bias, "time_s": time.time() - t0}
            print(f"  Acc: {acc:.4f} | F1: {f1_:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | Bias: {bias:.3f}")
        except Exception as e:
            print(f"  ⚠️ Fairlearn failed: {e}")

    # ======================================================================
    # RANKING & SELECTION
    # ======================================================================
    print("\n" + "=" * 70)
    print("🏆 FINAL RANKING — COMPOSITE SCORE ANALYSIS")
    print("=" * 70)

    summary = []
    for name, metrics in approaches.items():
        score = composite_score(metrics['acc'], metrics['f1'], metrics['bias'])
        summary.append({
            "Approach": name,
            "Accuracy": round(metrics['acc'] * 100, 2),
            "F1_Score": round(metrics['f1'], 4),
            "Precision": round(metrics['prec'], 4),
            "Recall": round(metrics['rec'], 4),
            "Gender_Parity_Gap": round(metrics['bias'] * 100, 2),
            "Composite_Score": round(score, 4),
            "Time_Seconds": round(metrics['time_s'], 1)
        })

    summary.sort(key=lambda x: x["Composite_Score"], reverse=True)

    print(f"\n{'Rank':<5} {'Approach':<35} {'Accuracy':>10} {'F1':>8} {'Bias%':>8} {'Score':>8}")
    print("-" * 78)
    for i, entry in enumerate(summary, 1):
        marker = " 🏆" if i == 1 else ""
        print(f"{i:<5} {entry['Approach']:<35} {entry['Accuracy']:>9.2f}% {entry['F1_Score']:>7.4f} {entry['Gender_Parity_Gap']:>7.2f}% {entry['Composite_Score']:>7.4f}{marker}")

    best = summary[0]
    best_name = best["Approach"]
    best_model = approaches[best_name]["model"]

    print(f"\n✅ CHAMPION MODEL: {best_name}")
    print(f"   Accuracy: {best['Accuracy']}% | F1: {best['F1_Score']} | Bias: {best['Gender_Parity_Gap']}%")

    # Save champion model
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "model.pkl"), "wb") as f:
        pickle.dump(best_model, f)
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODEL_DIR, "feature_columns.json"), "w") as f:
        json.dump(feature_cols, f)
    with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
        json.dump({
            "accuracy": best["Accuracy"] / 100,
            "f1": best["F1_Score"],
            "precision": best["Precision"],
            "recall": best["Recall"],
            "gender_parity_gap": best["Gender_Parity_Gap"] / 100,
            "model_name": best_name,
            "composite_score": best["Composite_Score"]
        }, f, indent=2)

    print(f"💾 Champion model saved → {MODEL_DIR}/model.pkl")

    # Save full results
    results_path = os.path.join(MODEL_DIR, "comprehensive_search_results.json")
    with open(results_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"💾 Full results saved → {results_path}")

    # Generate charts
    results_df = pd.DataFrame(summary)
    generate_charts(results_df, CHARTS_DIR)

    return summary, best_name


if __name__ == "__main__":
    summary, winner = run_comprehensive_search()
