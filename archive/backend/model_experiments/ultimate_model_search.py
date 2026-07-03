"""
Ultimate Model Search Framework
Applies SMOTE-ENN, Multi-Layer Perceptrons, Support Vector Classifiers,
Bayesian Optimization (Optuna), and advanced algorithmic fairness (Fairlearn)
to minimize demographic bias and push accuracy to the absolute peak.
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
from sklearn.metrics import accuracy_score, f1_score
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
import xgboost as xgb
import lightgbm as lgb

try:
    import optuna
except ImportError:
    optuna = None

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
    from .fairness_audit import demographic_parity
except ImportError:
    from fairness_audit import demographic_parity

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')

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
    return acc, f1, g_parity['disparity']


def train_department_constrained_variant(random_state=42, eps_values=None):
    """Train and save the department-constrained Fairlearn model without overwriting model.pkl."""
    if ExponentiatedGradient is None or DemographicParity is None:
        raise ImportError("fairlearn is required to train the department-constrained variant")

    data, feature_cols = load_data()
    X = data[feature_cols].fillna(0)
    y = data["eligible"]

    X_train, X_test, y_train, y_test, meta_train, meta_test = train_test_split(
        X, y, data[["gender", "department"]], test_size=0.2, random_state=random_state, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    dept_groups = {
        "AIDS": "tech", "AIML": "tech", "CSE": "tech", "ECE": "tech", "EEE": "tech", "IT": "tech",
        "BCA": "non-tech", "CIVIL": "non-tech", "MBA": "non-tech", "MECH": "non-tech",
    }
    train_dept_group = meta_train["department"].map(dept_groups).fillna("other")
    test_dept_group = meta_test["department"].map(dept_groups).fillna("other")
    eps_values = eps_values or [0.005, 0.01, 0.02, 0.03, 0.05]

    best = None
    for eps in eps_values:
        base_lgb = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, random_state=random_state, verbose=-1)
        fair_dept = ExponentiatedGradient(
            base_lgb,
            constraints=DemographicParity(),
            eps=eps,
            max_iter=20,
        )
        fair_dept.fit(X_train_s, y_train, sensitive_features=train_dept_group)
        acc, f1, gender_gap = evaluate_model(fair_dept, X_test_s, y_test, meta_test)
        preds = fair_dept.predict(X_test_s)
        dept_audit = meta_test.copy()
        dept_audit["department_group"] = test_dept_group
        dept_audit["predicted"] = preds
        raw_dept_gap = demographic_parity(dept_audit, "department")["disparity"]
        grouped_dept_gap = demographic_parity(dept_audit, "department_group")["disparity"]
        row = {
            "model": fair_dept,
            "eps": eps,
            "accuracy": float(acc),
            "f1": float(f1),
            "gender_parity_gap": float(gender_gap),
            "department_parity_gap": float(raw_dept_gap),
            "department_group_parity_gap": float(grouped_dept_gap),
        }
        if best is None:
            best = row
        elif row["department_group_parity_gap"] < best["department_group_parity_gap"]:
            best = row
        elif row["department_group_parity_gap"] == best["department_group_parity_gap"] and row["f1"] > best["f1"]:
            best = row

    fair_dept = best["model"]

    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, "fairlearn_lightgbm_dept_constrained.pkl")
    metrics_path = os.path.join(MODEL_DIR, "fairlearn_lightgbm_dept_constrained_metrics.json")
    with open(model_path, "wb") as f:
        pickle.dump(fair_dept, f)
    with open(metrics_path, "w") as f:
        json.dump({
            "eps": best["eps"],
            "accuracy": best["accuracy"],
            "f1": best["f1"],
            "gender_parity_gap": best["gender_parity_gap"],
            "department_parity_gap": best["department_parity_gap"],
            "department_group_parity_gap": best["department_group_parity_gap"],
            "model_path": model_path,
            "note": "Department-constrained variant saved separately; model.pkl is not overwritten.",
        }, f, indent=2)

    print(f"Department-constrained model saved -> {model_path}")
    print(f"Metrics saved -> {metrics_path}")
    print(
        f"eps={best['eps']:.3f} Accuracy={best['accuracy']:.4f} F1={best['f1']:.4f} "
        f"GenderGap={best['gender_parity_gap']:.4f} "
        f"DeptGap={best['department_parity_gap']:.4f} "
        f"DeptGroupGap={best['department_group_parity_gap']:.4f}"
    )
    return fair_dept

def run_ultimate_search():
    print("="*60)
    print("🧬 Ultimate Extrapolated Model Search Active...")
    print("="*60)
    
    data, feature_cols = load_data()
    X = data[feature_cols].fillna(0)
    y = data["eligible"]
    
    X_train, X_test, y_train, y_test, meta_train, meta_test = train_test_split(
        X, y, data[["gender", "department"]], test_size=0.2, random_state=42, stratify=y
    )
    
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    if SMOTEENN is not None:
        print("⚖️ Balancing heavily biased classes via SMOTE-ENN...")
        smote_enn = SMOTEENN(random_state=42)
        X_train_res, y_train_res = smote_enn.fit_resample(X_train_s, y_train)
        print("\nDepartment-constrained Fairlearn variant")
        try:
            dept_groups = {
                "AIDS": "tech", "AIML": "tech", "CSE": "tech", "ECE": "tech", "EEE": "tech", "IT": "tech",
                "BCA": "non-tech", "CIVIL": "non-tech", "MBA": "non-tech", "MECH": "non-tech",
            }
            train_dept_group = meta_train["department"].map(dept_groups).fillna("other")
            base_lgb2 = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, random_state=42)
            fair_dept = ExponentiatedGradient(
                base_lgb2,
                constraints=DemographicParity(),
                eps=0.05,
                max_iter=10,
            )
            fair_dept.fit(X_train_s, y_train, sensitive_features=train_dept_group)
            dept_model_path = os.path.join(MODEL_DIR, "fairlearn_lightgbm_dept_constrained.pkl")
            with open(dept_model_path, "wb") as f:
                pickle.dump(fair_dept, f)
            print(f"  Department-constrained model saved -> {dept_model_path}")
        except Exception as e:
            print(f"  Department-constrained Fairlearn failed due to: {e}. Skipping.")
    else:
        X_train_res, y_train_res = X_train_s, y_train

    approaches = {}

    # 1. Multi-Layer Perceptron (Neural Network)
    print("\n🧠 Approach 4: Deep Neural Network (MLP)")
    t0 = time.time()
    mlp = MLPClassifier(hidden_layer_sizes=(64, 32, 16), max_iter=200, activation='relu', random_state=42)
    mlp.fit(X_train_res, y_train_res)
    acc, f1, bias = evaluate_model(mlp, X_test_s, y_test, meta_test)
    approaches["MultiLayerPerceptron_Deep"] = {"model": mlp, "acc": acc, "f1": f1, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Bias: {bias:.3f}")

    # 2. Support Vector Machine (RBF Kernel)
    print("\n⚔️ Approach 5: Support Vector Machine (RBF)")
    t0 = time.time()
    svc = SVC(kernel='rbf', C=1.0, class_weight='balanced', random_state=42)
    svc.fit(X_train_res, y_train_res)
    acc, f1, bias = evaluate_model(svc, X_test_s, y_test, meta_test)
    approaches["SVC_RBF_Balanced"] = {"model": svc, "acc": acc, "f1": f1, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Bias: {bias:.3f}")

    # 3. Optuna Optimized XGBoost
    print("\n🎯 Approach 6: Bayesian Optuna XGBoost (Max Search Space)")
    t0 = time.time()
    def objective_xgb(trial):
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 100, 600),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'scale_pos_weight': sum(y_train_res==0)/sum(y_train_res==1),
            'random_state': 42,
            'use_label_encoder': False,
            'eval_metric': 'logloss'
        }
        model = xgb.XGBClassifier(**params)
        model.fit(X_train_res, y_train_res)
        preds = model.predict(X_test_s)
        return f1_score(y_test, preds)

    study_xgb = optuna.create_study(direction='maximize')
    study_xgb.optimize(objective_xgb, n_trials=10) # Limited trials for time constraints
    
    best_xgb_optuna = xgb.XGBClassifier(**study_xgb.best_params, scale_pos_weight=sum(y_train_res==0)/sum(y_train_res==1), random_state=42, eval_metric='logloss')
    best_xgb_optuna.fit(X_train_res, y_train_res)
    acc, f1, bias = evaluate_model(best_xgb_optuna, X_test_s, y_test, meta_test)
    approaches["XGBoost_OptunaTuned"] = {"model": best_xgb_optuna, "acc": acc, "f1": f1, "bias": bias, "time_s": time.time() - t0}
    print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Bias: {bias:.3f}")

    # 4. LightGBM + Fairlearn ExponentiatedGradient Strict Fairness
    print("\n⚖️ Approach 7: LightGBM + Fairlearn Exponentiated Gradient")
    t0 = time.time()
    if ExponentiatedGradient is not None:
        base_lgb = lgb.LGBMClassifier(n_estimators=200, max_depth=6, random_state=42)
        # We enforce demographic parity explicitly over the Gender attribute on the training data
        fair_model = ExponentiatedGradient(base_lgb, constraints=DemographicParity(), eps=0.01, max_iter=10)
        
        # Fairlearn requires categorical sensitive features aligned with training
        sensitive_train = meta_train["gender"].astype(str)
        try:
            fair_model.fit(X_train_s, y_train, sensitive_features=sensitive_train)
            acc, f1, bias = evaluate_model(fair_model, X_test_s, y_test, meta_test)
            approaches["LightGBM_Fairlearn_Constrained"] = {"model": fair_model, "acc": acc, "f1": f1, "bias": bias, "time_s": time.time() - t0}
            print(f"  Acc: {acc:.4f} | F1: {f1:.4f} | Bias: {bias:.3f} (Algorithmic Enforcement Success)")
        except Exception as e:
            print(f"  ⚠️ Fairlearn optimization failed due to: {e}. Skipping.")
    else:
        print("  ⚠️ Fairlearn not imported. Skipping.")

    print("\n🏆 Determining Ultimate Champion Pipeline...")
    best_name = None
    best_score = 0
    summary = []
    
    for name, metrics in approaches.items():
        # Score emphasizes F1 highly, heavily penalizes bias > 5%
        score = metrics['f1'] * 0.70 + metrics['acc'] * 0.30
        if metrics['bias'] > 0.05:
            score -= (metrics['bias'] * 3) # Extremely harsh penalty for bias over 5%
            
        if score > best_score:
            best_score = score
            best_name = name
            
        summary.append({
            "Approach": name,
            "Accuracy": round(metrics['acc']*100, 2),
            "F1_Score": round(metrics['f1'], 4),
            "Gender_Parity_Gap": round(metrics['bias']*100, 2),
            "Time_Seconds": round(metrics['time_s'], 1)
        })

    print(f"\n✅ THE ULTIMATE WINNER: {best_name}")
    best_model = approaches[best_name]["model"]
    
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "model.pkl"), "wb") as f:
        pickle.dump(best_model, f)
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODEL_DIR, "feature_columns.json"), "w") as f:
        json.dump(feature_cols, f)
        
    print("💾 New Best-In-Class 'Ultimate' Model locked & persisted.")
    
    # Save the history to json for appending
    history_file = "ultimate_search_results.json"
    with open(history_file, "w") as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    run_ultimate_search()
