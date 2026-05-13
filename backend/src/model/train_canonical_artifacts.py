import json
import os
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

from app.services.artifact_registry import CANONICAL_ARTIFACTS, save_json, save_pickle
from src.model.rank_train import FEATURE_COLS as RANKER_FEATURE_COLS, build_group_array, load_ranking_data, make_ranker
from src.model.train import FEATURE_COLS as CLASSIFIER_FEATURE_COLS, load_training_data, make_classifier, train_model_with_cv

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def train_canonical_baseline() -> Dict[str, float]:
    data = load_training_data()
    model, scaler, metrics, cv_results = train_model_with_cv(data)

    artifact = CANONICAL_ARTIFACTS["baseline_classifier"]
    save_pickle(artifact["model"], model)
    save_pickle(artifact["scaler"], scaler)
    save_json(artifact["features"], CLASSIFIER_FEATURE_COLS)
    save_json(artifact["metrics"], {**metrics, "cv_results": cv_results, "trained_on": "canonical_data"})
    return metrics


def train_canonical_fair_champion() -> Dict[str, float]:
    try:
        import lightgbm as lgb  # type: ignore
        from fairlearn.reductions import DemographicParity, ExponentiatedGradient  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"Fairness training dependencies unavailable: {exc}")

    data = load_training_data().copy()
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))[["student_id", "gender", "department"]]
    data = data.merge(students, on="student_id", how="left")

    X = data[CLASSIFIER_FEATURE_COLS].fillna(0)
    y = data["eligible"].astype(int)
    sensitive = data["gender"].fillna("Unknown").astype(str)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    base = lgb.LGBMClassifier(n_estimators=200, max_depth=6, learning_rate=0.05, random_state=42, verbose=-1)
    fair_model = ExponentiatedGradient(base, constraints=DemographicParity(), eps=0.01, max_iter=15)
    fair_model.fit(X_scaled, y, sensitive_features=sensitive)

    probabilities = fair_model.predict(X_scaled)
    predictions = np.asarray(probabilities, dtype=int)
    metrics = {
        "accuracy": float(accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "epsilon": 0.01,
        "trained_on": "canonical_data",
    }

    artifact = CANONICAL_ARTIFACTS["fair_champion"]
    save_pickle(
        artifact["bundle"],
        {
            "model": fair_model,
            "scaler": scaler,
            "feature_cols": CLASSIFIER_FEATURE_COLS,
            "epsilon": 0.01,
            "trained_on": "canonical_data",
        },
    )
    save_json(artifact["metrics"], metrics)
    return metrics


def train_canonical_ranker() -> Dict[str, float]:
    ranking_data = load_ranking_data()
    X = ranking_data[RANKER_FEATURE_COLS].fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    y = ranking_data["relevance_grade"].values
    group = build_group_array(ranking_data)

    ranker = make_ranker(42)
    ranker.fit(X_scaled, y, group=group, verbose=False)
    scores = ranker.predict(X_scaled)

    metrics = {
        "trained_on": "canonical_data",
        "num_pairs": int(len(ranking_data)),
        "num_queries": int(ranking_data["group_id"].nunique()),
        "score_mean": float(np.mean(scores)),
        "score_std": float(np.std(scores)),
    }

    artifact = CANONICAL_ARTIFACTS["ranker"]
    save_pickle(artifact["model"], ranker)
    save_pickle(artifact["scaler"], scaler)
    save_json(artifact["features"], RANKER_FEATURE_COLS)
    save_json(artifact["metrics"], metrics)
    return metrics


def main():
    print("=" * 72)
    print("Training canonical JobSwipe artifacts from canonical CSV data")
    print("=" * 72)

    baseline_metrics = train_canonical_baseline()
    print(f"Baseline classifier trained: acc={baseline_metrics['accuracy']:.4f} f1={baseline_metrics['f1']:.4f}")

    fair_metrics = train_canonical_fair_champion()
    print(f"Fair champion trained: acc={fair_metrics['accuracy']:.4f} f1={fair_metrics['f1']:.4f}")

    ranker_metrics = train_canonical_ranker()
    print(
        "Canonical ranker trained: "
        f"queries={ranker_metrics['num_queries']} pairs={ranker_metrics['num_pairs']}"
    )

    print("\nSaved canonical artifacts:")
    print(json.dumps(CANONICAL_ARTIFACTS, indent=2))


if __name__ == "__main__":
    main()
