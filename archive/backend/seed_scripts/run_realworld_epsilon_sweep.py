"""
Train a real-world-only Fairlearn epsilon sweep and generate matching charts.

This uses backend/data/resume_realworld_normalized as the only data source.
Because the current real-world cohort has no usable gender variation, the
fairness constraint and parity audit use department as the sensitive feature.
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

try:
    import lightgbm as lgb  # type: ignore
    from fairlearn.reductions import DemographicParity, ExponentiatedGradient  # type: ignore
except Exception as exc:  # pragma: no cover - runtime dependency guard
    raise RuntimeError(f"Real-world epsilon sweep requires lightgbm and fairlearn: {exc}")

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from src.model.train import FEATURE_COLS as CLASSIFIER_FEATURE_COLS

DATA_DIR = BACKEND_DIR / "data" / "resume_realworld_normalized"
MODEL_DIR = BACKEND_DIR / "models"
CHARTS_DIR = MODEL_DIR / "charts"
PREFIX = "resume_realworld"
EPS_VALUES = [0.005, 0.010, 0.015, 0.017, 0.019, 0.020, 0.025, 0.028, 0.029, 0.034, 0.040, 0.050]
RESULTS_PATH = MODEL_DIR / f"{PREFIX}_epsilon_sweep_results.json"


def load_training_frame() -> pd.DataFrame:
    pairs = pd.read_csv(DATA_DIR / "pair_features.csv")
    labels = pd.read_csv(DATA_DIR / "training_labels.csv")
    students = pd.read_csv(DATA_DIR / "students.csv")[["student_id", "gender", "department"]]
    frame = pairs.merge(labels[["student_id", "company_id", "eligible"]], on=["student_id", "company_id"])
    return frame.merge(students, on="student_id", how="left")


def parity_gap(predictions: np.ndarray, sensitive: pd.Series) -> float:
    audit = pd.DataFrame({
        "predicted": predictions.astype(int),
        "sensitive": sensitive.fillna("Unknown").astype(str),
    })
    rates = audit.groupby("sensitive")["predicted"].mean()
    if len(rates) < 2:
        return 0.0
    return float(rates.max() - rates.min())


def composite_score(accuracy: float, f1: float, parity: float) -> float:
    score = (f1 * 0.70) + (accuracy * 0.30)
    if parity > 0.03:
        score -= parity * 4
    return float(score)


def sweep() -> List[Dict[str, Any]]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_training_frame()
    X = frame[CLASSIFIER_FEATURE_COLS].fillna(0)
    y = frame["eligible"].astype(int)
    sensitive = frame["department"].fillna("Unknown").astype(str)

    X_train, X_test, y_train, y_test, sensitive_train, sensitive_test = train_test_split(
        X,
        y,
        sensitive,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    results: List[Dict[str, Any]] = []
    for eps in EPS_VALUES:
        print(f"Training real-world Fairlearn LightGBM epsilon={eps:.3f}")
        base = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            random_state=42,
            verbose=-1,
        )
        model = ExponentiatedGradient(
            base,
            constraints=DemographicParity(),
            eps=eps,
            max_iter=15,
        )
        model.fit(X_train_scaled, y_train, sensitive_features=sensitive_train)
        predictions = np.asarray(model.predict(X_test_scaled), dtype=int)
        accuracy = float(accuracy_score(y_test, predictions))
        f1 = float(f1_score(y_test, predictions, zero_division=0))
        precision = float(precision_score(y_test, predictions, zero_division=0))
        recall = float(recall_score(y_test, predictions, zero_division=0))
        gap = parity_gap(predictions, sensitive_test)
        row = {
            "eps": float(eps),
            "accuracy": round(accuracy * 100, 3),
            "f1": round(f1, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "department_parity_gap": round(gap * 100, 3),
            "sensitive_feature": "department",
            "composite_score": round(composite_score(accuracy, f1, gap), 4),
        }
        results.append(row)
        with (MODEL_DIR / f"{PREFIX}_fairlearn_lightgbm_eps_{eps:.3f}.pkl").open("wb") as handle:
            pickle.dump({
                "model": model,
                "scaler": scaler,
                "feature_cols": CLASSIFIER_FEATURE_COLS,
                "epsilon": eps,
                "sensitive_feature": "department",
                "trained_on": "resume_realworld",
            }, handle)

    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def save_epsilon_chart(results: List[Dict[str, Any]]) -> Path:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = sorted(results, key=lambda row: row["eps"])
    eps = [row["eps"] for row in rows]
    accuracy = [row["accuracy"] for row in rows]
    f1 = [row["f1"] * 100 for row in rows]
    parity = [row["department_parity_gap"] for row in rows]

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.plot(eps, accuracy, "o-", color="#2563eb", label="Accuracy (%)", linewidth=2)
    ax1.plot(eps, f1, "s--", color="#0f766e", label="F1 x 100", linewidth=1.6)
    ax1.set_xlabel("Fairlearn epsilon")
    ax1.set_ylabel("Model quality (%)")
    ax1.grid(alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(eps, parity, "^-", color="#dc2626", label="Department parity gap (%)", linewidth=2)
    ax2.axhline(y=10, color="#dc2626", linestyle=":", alpha=0.55, linewidth=1.4)
    ax2.set_ylabel("Department parity gap (%)")

    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [line.get_label() for line in lines], loc="center right")
    ax1.set_title("Real-world Fairlearn Epsilon Sweep (Department Parity)", fontweight="bold")
    fig.tight_layout()
    out = CHARTS_DIR / f"{PREFIX}_epsilon_sweep.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def save_pareto_chart(results: List[Dict[str, Any]]) -> Path:
    rows = sorted(results, key=lambda row: row["accuracy"])
    x = [row["accuracy"] for row in rows]
    y = [row["department_parity_gap"] for row in rows]
    labels = [f"eps={row['eps']:.3f}" for row in rows]

    pareto = []
    for i in range(len(rows)):
        dominated = any(
            j != i and x[j] >= x[i] and y[j] <= y[i] and (x[j] > x[i] or y[j] < y[i])
            for j in range(len(rows))
        )
        if not dominated:
            pareto.append(i)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.scatter(x, y, c="#93c5fd", s=95, edgecolors="#1d4ed8", linewidths=0.8, zorder=3)
    for label, xi, yi in zip(labels, x, y):
        ax.annotate(label, (xi, yi), xytext=(5, 5), textcoords="offset points", fontsize=8, color="#334155")
    if pareto:
        pareto_sorted = sorted(pareto, key=lambda index: x[index])
        ax.plot([x[i] for i in pareto_sorted], [y[i] for i in pareto_sorted], "r--", linewidth=1.8, label="Pareto frontier")
    best_idx = max(range(len(rows)), key=lambda index: rows[index]["composite_score"])
    ax.scatter([x[best_idx]], [y[best_idx]], c="#facc15", s=260, marker="*", edgecolors="#b45309", linewidths=1.2, label="Best composite")
    ax.axhline(y=10, color="#dc2626", linestyle=":", alpha=0.55, linewidth=1.4, label="10% threshold")
    ax.set_xlabel("Accuracy (%)")
    ax.set_ylabel("Department parity gap (%)")
    ax.set_title("Real-world Accuracy-Fairness Pareto Frontier", fontweight="bold")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    out = CHARTS_DIR / f"{PREFIX}_pareto_frontier.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def save_f1_chart(results: List[Dict[str, Any]]) -> Path:
    rows = sorted(results, key=lambda row: row["f1"])
    labels = [f"eps={row['eps']:.3f}" for row in rows]
    values = [row["f1"] * 100 for row in rows]
    colors = plt.cm.plasma(np.linspace(0.2, 0.9, len(rows)))
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(labels, values, color=colors, edgecolor="white", height=0.6)
    ax.set_title("Real-world Fairlearn F1 Comparison", fontsize=14, fontweight="bold")
    ax.set_xlabel("F1 score (%)")
    ax.set_xlim(0, 100)
    ax.grid(axis="x", alpha=0.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2, f"{value:.2f}%", va="center", fontsize=8)
    fig.tight_layout()
    out = CHARTS_DIR / f"{PREFIX}_f1_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def save_composite_chart(results: List[Dict[str, Any]]) -> Path:
    rows = sorted(results, key=lambda row: row["composite_score"])
    labels = [f"eps={row['eps']:.3f}" for row in rows]
    values = [row["composite_score"] for row in rows]
    colors = plt.cm.coolwarm(np.linspace(0.15, 0.9, len(rows)))
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(labels, values, color=colors, edgecolor="white", height=0.6)
    ax.set_title("Real-world Composite Score Ranking", fontsize=14, fontweight="bold")
    ax.set_xlabel("Composite score")
    ax.grid(axis="x", alpha=0.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2, f"{value:.4f}", va="center", fontsize=8)
    fig.tight_layout()
    out = CHARTS_DIR / f"{PREFIX}_composite_score_ranking.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def save_combined_dashboard(results: List[Dict[str, Any]]) -> Path:
    rows = pd.DataFrame(results).sort_values("eps")
    labels = [f"{eps:.3f}" for eps in rows["eps"]]
    fig, axes = plt.subplots(1, 3, figsize=(19, 7))

    axes[0].bar(labels, rows["accuracy"], color="#2563eb")
    axes[0].set_title("Accuracy (%)", fontweight="bold")
    axes[0].set_ylim(0, 100)
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].bar(labels, rows["f1"] * 100, color="#0f766e")
    axes[1].set_title("F1 (%)", fontweight="bold")
    axes[1].set_ylim(0, 100)
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].grid(axis="y", alpha=0.25)

    colors = ["#22c55e" if value < 5 else "#f59e0b" if value < 10 else "#ef4444" for value in rows["department_parity_gap"]]
    axes[2].bar(labels, rows["department_parity_gap"], color=colors)
    axes[2].set_title("Department parity gap (%)", fontweight="bold")
    axes[2].axhline(y=10, color="#dc2626", linestyle="--", linewidth=1.4)
    axes[2].tick_params(axis="x", rotation=45)
    axes[2].grid(axis="y", alpha=0.25)

    fig.suptitle("Real-world Fairlearn Epsilon Sweep Dashboard", fontsize=16, fontweight="bold")
    fig.tight_layout()
    out = CHARTS_DIR / f"{PREFIX}_combined_dashboard.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    charts_only = "--charts-only" in sys.argv
    if charts_only and RESULTS_PATH.exists():
        results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    else:
        results = sweep()
    epsilon_chart = save_epsilon_chart(results)
    pareto_chart = save_pareto_chart(results)
    f1_chart = save_f1_chart(results)
    composite_chart = save_composite_chart(results)
    combined_chart = save_combined_dashboard(results)
    print(json.dumps({
        "results": f"{PREFIX}_epsilon_sweep_results.json",
        "charts": [
            combined_chart.name,
            composite_chart.name,
            epsilon_chart.name,
            f1_chart.name,
            pareto_chart.name,
        ],
        "sensitive_feature": "department",
        "data_source": str(DATA_DIR),
    }, indent=2))


if __name__ == "__main__":
    main()
