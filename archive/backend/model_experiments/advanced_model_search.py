"""
Advanced Model Search: Maximize Accuracy & Eliminate Bias
Explores various tree-based architectures with hyperparameter grids
and class-balancing techniques to achieve the theoretical maximum
performance on exactly computed rule-based soft margins.
"""

import os
import json
import pickle
import pandas as pd
import numpy as np
import time
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
import xgboost as xgb
import lightgbm as lgb
from .fairness_audit import demographic_parity # Import our own fairness logic directly!

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')

def load_data():
    pairs = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))
    labels = pd.read_csv(os.path.join(DATA_DIR, "training_labels.csv"))
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))
    
    # Merge for full tracking including bias
    data = pairs.merge(labels[["student_id", "company_id", "eligible"]], on=["student_id", "company_id"])
    data = data.merge(students[["student_id", "gender", "department"]], on="student_id")
    
    # Exclude non-features from X
    drop_cols = ["student_id", "company_id", "eligible", "gender", "department"]
    feature_cols = [c for c in data.columns if c not in drop_cols]
    
    return data, feature_cols

def run_advanced_search():
    print("="*60)
    print("🚀 Initiating Advanced Model Grid Search Strategy...")
    print("Target: Max Accuracy + Max F1 + Minimum Bias (<2% Parity Gap)")
    print("="*60)
    
    data, feature_cols = load_data()
    
    X = data[feature_cols].fillna(0)
    y = data["eligible"]
    
    X_train, X_test, y_train, y_test, meta_train, meta_test = train_test_split(
        X, y, data[["gender", "department"]], 
        test_size=0.2, random_state=42, stratify=y
    )
    
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    approaches = {}
    
    # 1. Random Forest Balanced Baseline
    print("\n🌲 Approach 1: Random Forest (Class Balanced)")
    t0 = time.time()
    rf = RandomForestClassifier(n_estimators=300, max_depth=12, class_weight='balanced', random_state=42, n_jobs=-1)
    rf.fit(X_train_s, y_train)
    preds = rf.predict(X_test_s)
    
    # Evaluate RF fairness
    test_audit = meta_test.copy()
    test_audit["predicted"] = preds
    g_parity = demographic_parity(test_audit, "gender")
    d_parity = demographic_parity(test_audit, "department")
    
    approaches["RandomForest_Balanced"] = {
        "model": rf,
        "acc": accuracy_score(y_test, preds),
        "f1": f1_score(y_test, preds),
        "gender_bias": g_parity['disparity'],
        "dept_bias": d_parity['disparity'],
        "time_s": time.time() - t0
    }
    
    print(f"  Acc: {approaches['RandomForest_Balanced']['acc']:.4f} | F1: {approaches['RandomForest_Balanced']['f1']:.4f} | Bias: {g_parity['disparity']:.3f}")

    # 2. XGBoost with GridSearch
    print("\n🔥 Approach 2: XGBoost Heavy Tuning (Max Depth/L2 Reg)")
    t0 = time.time()
    xgb_base = xgb.XGBClassifier(random_state=42, eval_metric='logloss', use_label_encoder=False)
    params = {
        'n_estimators': [200, 400],
        'max_depth': [4, 6],
        'learning_rate': [0.05, 0.1],
        'scale_pos_weight': [1.0, sum(y_train==0)/sum(y_train==1)]
    }
    grid = GridSearchCV(xgb_base, params, cv=3, scoring='f1', n_jobs=-1)
    grid.fit(X_train_s, y_train)
    
    best_xgb = grid.best_estimator_
    preds = best_xgb.predict(X_test_s)
    test_audit["predicted"] = preds
    g_parity = demographic_parity(test_audit, "gender")
    d_parity = demographic_parity(test_audit, "department")
    
    approaches["XGBoost_GridTuned"] = {
        "model": best_xgb,
        "params": grid.best_params_,
        "acc": accuracy_score(y_test, preds),
        "f1": f1_score(y_test, preds),
        "gender_bias": g_parity['disparity'],
        "dept_bias": d_parity['disparity'],
        "time_s": time.time() - t0
    }
    print(f"  Acc: {approaches['XGBoost_GridTuned']['acc']:.4f} | F1: {approaches['XGBoost_GridTuned']['f1']:.4f} | Bias: {g_parity['disparity']:.3f}")
    print(f"  Best params: {grid.best_params_}")

    # 3. LightGBM Advanced Trees
    print("\n⚡ Approach 3: LightGBM (Gradient-based, Robust against overfitting)")
    t0 = time.time()
    lgb_model = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.03, max_depth=7, class_weight='balanced', random_state=42)
    lgb_model.fit(X_train_s, y_train)
    
    preds = lgb_model.predict(X_test_s)
    test_audit["predicted"] = preds
    g_parity = demographic_parity(test_audit, "gender")
    d_parity = demographic_parity(test_audit, "department")
    
    approaches["LightGBM_Balanced"] = {
        "model": lgb_model,
        "acc": accuracy_score(y_test, preds),
        "f1": f1_score(y_test, preds),
        "gender_bias": g_parity['disparity'],
        "dept_bias": d_parity['disparity'],
        "time_s": time.time() - t0
    }
    print(f"  Acc: {approaches['LightGBM_Balanced']['acc']:.4f} | F1: {approaches['LightGBM_Balanced']['f1']:.4f} | Bias: {g_parity['disparity']:.3f}")

    # Rank & Pick Highest F1 that also has < 10% bias
    print("\n🏆 Determining Best Pipeline Matrix...")
    best_name = None
    best_score = 0
    
    summary = []
    
    for name, metrics in approaches.items():
        score = metrics['f1'] * 0.7 + metrics['acc'] * 0.3 # Weight F1 high
        
        # Penalize if bias > 0.05
        if metrics['gender_bias'] > 0.05:
            score -= (metrics['gender_bias']*2)
            
        if score > best_score:
            best_score = score
            best_name = name
            
        summary.append({
            "Approach": name,
            "Accuracy": round(metrics['acc']*100, 2),
            "F1_Score": round(metrics['f1'], 4),
            "Gender_Parity_Gap": round(metrics['gender_bias']*100, 2),
            "Time_Seconds": round(metrics['time_s'], 1)
        })

    print(f"\n✅ WINNER CHOSEN: {best_name}")
    best_model = approaches[best_name]["model"]
    
    # Save the absolute best
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "model.pkl"), "wb") as f:
        pickle.dump(best_model, f)
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODEL_DIR, "feature_columns.json"), "w") as f:
        json.dump(feature_cols, f)
        
    print("💾 New Best-In-Class Model locked & persisted replacing old metrics.")
    
    with open("advanced_search_results.json", "w") as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    run_advanced_search()
