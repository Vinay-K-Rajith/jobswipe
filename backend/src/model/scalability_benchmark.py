import json
import os
import pickle
import time

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


def _time_mean(fn, repeats=3):
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        timings.append((time.perf_counter() - start) * 1000)
    return float(np.mean(timings))


def _metric_row(total_ms, n_students, n_companies):
    pairs = max(n_students * n_companies, 1)
    return {
        "total_ms": round(total_ms, 3),
        "per_student_ms": round(total_ms / max(n_students, 1), 3),
        "per_pair_ms": round(total_ms / pairs, 6),
    }


def main():
    with open(os.path.join(MODEL_DIR, "model.pkl"), "rb") as f:
        classifier = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "rb") as f:
        scaler = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "feature_columns.json")) as f:
        feature_cols = json.load(f)

    with open(os.path.join(MODEL_DIR, "ranker.pkl"), "rb") as f:
        ranker = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "ranker_scaler.pkl"), "rb") as f:
        ranker_scaler = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "ranker_feature_columns.json")) as f:
        ranker_feature_cols = json.load(f)

    pairs = pd.read_csv(os.path.join(DATA_DIR, "pair_features.csv"))
    n_companies = int(pairs["company_id"].nunique())
    results = {"classifier": {}, "ranker": {}}

    for n in [1, 10, 100, 800]:
        student_ids = pairs["student_id"].drop_duplicates().head(n)
        subset = pairs[pairs["student_id"].isin(student_ids)].copy()

        X_classifier = subset[feature_cols].fillna(0)
        classifier_scaled = scaler.transform(X_classifier)
        total_ms = _time_mean(lambda: classifier.predict_proba(classifier_scaled))
        results["classifier"][f"n_{n}"] = _metric_row(total_ms, len(student_ids), n_companies)

        X_ranker = subset[ranker_feature_cols].fillna(0)
        ranker_scaled = ranker_scaler.transform(X_ranker)
        total_ms = _time_mean(lambda: ranker.predict(ranker_scaled))
        results["ranker"][f"n_{n}"] = _metric_row(total_ms, len(student_ids), n_companies)

    if "n_800" in results["classifier"]:
        scale = 5000 / 800
        results["projected_5000"] = {
            "note": "Linear extrapolation from 800-student measurements",
            "classifier_total_ms": round(results["classifier"]["n_800"]["total_ms"] * scale, 3),
            "ranker_total_ms": round(results["ranker"]["n_800"]["total_ms"] * scale, 3),
        }

    out = os.path.join(MODEL_DIR, "scalability_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
