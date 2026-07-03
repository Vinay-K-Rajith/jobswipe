"""
Generate comparison charts for canonical vs real-world resume artifacts.

The charts are intentionally read-only over existing JSON/CSV artifacts. Run:
    python -m src.model.generate_realworld_comparison_charts
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BACKEND_DIR / "models"
CHARTS_DIR = MODEL_DIR / "charts"
REALWORLD_DATA_DIR = BACKEND_DIR / "data" / "resume_realworld_normalized"
REALWORLD_PARSED_DIR = BACKEND_DIR / "data" / "resume_realworld_parsed"
CANONICAL_DATA_DIR = BACKEND_DIR / "data"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def metric(payload: Dict[str, Any], name: str, default: float = 0.0) -> float:
    value = payload.get(name, default)
    return float(value or default)


def percent(value: float) -> float:
    return value * 100 if value <= 1 else value


def save_bar_chart(
    filename: str,
    title: str,
    labels: List[str],
    values: List[float],
    ylabel: str,
    colors: List[str],
    ylim: tuple[float, float] | None = None,
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=0.8)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=12)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )
    fig.tight_layout()
    out = CHARTS_DIR / filename
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def build_model_rows() -> List[Dict[str, Any]]:
    canonical_baseline = read_json(MODEL_DIR / "canonical_baseline_metrics.json", {})
    canonical_fair = read_json(MODEL_DIR / "canonical_fair_champion_metrics.json", {})
    canonical_ranker = read_json(MODEL_DIR / "canonical_ranker_metrics.json", {})
    real_baseline = read_json(MODEL_DIR / "resume_realworld_baseline_metrics.json", {})
    real_fair = read_json(MODEL_DIR / "resume_realworld_fair_champion_metrics.json", {})
    real_ranker = read_json(MODEL_DIR / "resume_realworld_ranker_metrics.json", {})

    return [
        {
            "dataset": "Canonical",
            "model": "Baseline",
            "accuracy": percent(metric(canonical_baseline, "accuracy")),
            "precision": percent(metric(canonical_baseline, "precision")),
            "recall": percent(metric(canonical_baseline, "recall")),
            "f1": percent(metric(canonical_baseline, "f1")),
            "ranker_ndcg10": 0.0,
            "ranker_precision10": 0.0,
        },
        {
            "dataset": "Canonical",
            "model": "Fair Champion",
            "accuracy": percent(metric(canonical_fair, "accuracy")),
            "precision": percent(metric(canonical_fair, "precision")),
            "recall": percent(metric(canonical_fair, "recall")),
            "f1": percent(metric(canonical_fair, "f1")),
            "ranker_ndcg10": 0.0,
            "ranker_precision10": 0.0,
        },
        {
            "dataset": "Canonical",
            "model": "Ranker",
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "ranker_ndcg10": percent(metric(canonical_ranker, "ndcg@10", metric(canonical_ranker, "ndcg@10_mean"))),
            "ranker_precision10": percent(metric(canonical_ranker, "precision@10", metric(canonical_ranker, "precision@10_mean"))),
        },
        {
            "dataset": "Real-world",
            "model": "Baseline",
            "accuracy": percent(metric(real_baseline, "accuracy")),
            "precision": percent(metric(real_baseline, "precision")),
            "recall": percent(metric(real_baseline, "recall")),
            "f1": percent(metric(real_baseline, "f1")),
            "ranker_ndcg10": 0.0,
            "ranker_precision10": 0.0,
        },
        {
            "dataset": "Real-world",
            "model": "Fair Champion",
            "accuracy": percent(metric(real_fair, "accuracy")),
            "precision": percent(metric(real_fair, "precision")),
            "recall": percent(metric(real_fair, "recall")),
            "f1": percent(metric(real_fair, "f1")),
            "ranker_ndcg10": 0.0,
            "ranker_precision10": 0.0,
        },
        {
            "dataset": "Real-world",
            "model": "Ranker",
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "ranker_ndcg10": percent(metric(real_ranker, "ndcg@10", metric(real_ranker, "ndcg@10_mean"))),
            "ranker_precision10": percent(metric(real_ranker, "precision@10", metric(real_ranker, "precision@10_mean"))),
        },
    ]


def dataset_profile_rows() -> pd.DataFrame:
    rows = []
    for label, data_dir in [("Canonical", CANONICAL_DATA_DIR), ("Real-world", REALWORLD_DATA_DIR)]:
        students = pd.read_csv(data_dir / "students.csv")
        companies = pd.read_csv(data_dir / "companies.csv")
        pairs_path = data_dir / "pair_features.csv"
        rows.append({
            "dataset": label,
            "students": len(students),
            "companies": len(companies),
            "pairs": len(pd.read_csv(pairs_path)) if pairs_path.exists() else 0,
            "avg_cgpa": float(students["cgpa"].mean()),
            "active_backlog_rate": float((students["active_backlogs"] > 0).mean() * 100),
        })
    return pd.DataFrame(rows)


def plot_model_metric_comparison(rows: List[Dict[str, Any]]) -> Path:
    df = pd.DataFrame([row for row in rows if row["model"] != "Ranker"])
    labels = [f"{row.dataset}\n{row.model}" for row in df.itertuples()]
    colors = ["#64748b", "#0f766e", "#2563eb", "#16a34a"]
    x = np.arange(len(labels))
    width = 0.2

    fig, ax = plt.subplots(figsize=(12, 7))
    for offset, metric_name, color in [
        (-1.5, "accuracy", "#2563eb"),
        (-0.5, "precision", "#0f766e"),
        (0.5, "recall", "#f59e0b"),
        (1.5, "f1", "#16a34a"),
    ]:
        ax.bar(x + offset * width, df[metric_name], width, label=metric_name.title(), color=color)
    ax.set_title("Canonical vs Real-world Classifier Metrics", fontsize=14, fontweight="bold")
    ax.set_ylabel("Score (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    out = CHARTS_DIR / "canonical_vs_realworld_model_metrics.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_ranker_comparison(rows: List[Dict[str, Any]]) -> Path:
    df = pd.DataFrame([row for row in rows if row["model"] == "Ranker"])
    labels = df["dataset"].tolist()
    x = np.arange(len(labels))
    width = 0.28
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.bar(x - width / 2, df["ranker_ndcg10"], width, label="NDCG@10", color="#7c3aed")
    ax.bar(x + width / 2, df["ranker_precision10"], width, label="Precision@10", color="#0891b2")
    ax.set_title("Ranker Quality Comparison", fontsize=14, fontweight="bold")
    ax.set_ylabel("Score (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 110)
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    out = CHARTS_DIR / "canonical_vs_realworld_ranker_metrics.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_dataset_profile() -> Path:
    df = dataset_profile_rows()
    metrics = ["students", "companies", "pairs"]
    x = np.arange(len(metrics))
    width = 0.32
    fig, ax = plt.subplots(figsize=(11, 6))
    for idx, row in enumerate(df.itertuples()):
        values = [getattr(row, metric_name) for metric_name in metrics]
        ax.bar(x + (idx - 0.5) * width, values, width, label=row.dataset)
    ax.set_title("Dataset Scale Comparison", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(["Students", "Companies", "Student-company pairs"])
    ax.set_ylabel("Count")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    out = CHARTS_DIR / "canonical_vs_realworld_dataset_profile.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_bias_audit() -> Path:
    canonical = read_json(MODEL_DIR / "criteria_bias_report.json", {}).get("summary", {})
    real = read_json(MODEL_DIR / "resume_realworld_criteria_bias_report.json", {}).get("summary", {})
    labels = ["Canonical", "Real-world"]
    flag_rates = [percent(metric(canonical, "flag_rate")), percent(metric(real, "flag_rate"))]
    flagged = [metric(canonical, "n_flagged"), metric(real, "n_flagged")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(labels, flag_rates, color=["#ef4444", "#22c55e"])
    axes[0].set_title("Bias Flag Rate")
    axes[0].set_ylabel("Companies flagged (%)")
    axes[0].set_ylim(0, max(10, max(flag_rates) + 5))
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(labels, flagged, color=["#ef4444", "#22c55e"])
    axes[1].set_title("Flagged Companies")
    axes[1].set_ylabel("Count")
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("Criteria Bias Audit Comparison", fontsize=14, fontweight="bold")
    fig.tight_layout()
    out = CHARTS_DIR / "canonical_vs_realworld_bias_audit.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_parser_robustness() -> Path | None:
    metrics = read_json(REALWORLD_PARSED_DIR / "parser_robustness_metrics.json", {})
    by_format = metrics.get("by_format") or {}
    if not by_format:
        return None
    labels = list(by_format.keys())
    cgpa_accuracy = [float(by_format[label].get("cgpa_accuracy") or 0) * 100 for label in labels]
    dept_accuracy = [float(by_format[label].get("department_accuracy") or 0) * 100 for label in labels]
    skill_recall = [float(by_format[label].get("avg_skill_recall") or 0) * 100 for label in labels]
    x = np.arange(len(labels))
    width = 0.24
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - width, cgpa_accuracy, width, label="CGPA accuracy", color="#2563eb")
    ax.bar(x, dept_accuracy, width, label="Department accuracy", color="#0f766e")
    ax.bar(x + width, skill_recall, width, label="Skill recall", color="#f59e0b")
    ax.set_title("Real-world Resume Parser Robustness by Format", fontsize=14, fontweight="bold")
    ax.set_ylabel("Score (%)")
    ax.set_xticks(x)
    ax.set_xticklabels([label.replace("_", "\n") for label in labels])
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    out = CHARTS_DIR / "resume_realworld_parser_robustness.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_realworld_summary(rows: List[Dict[str, Any]]) -> Path:
    real = pd.DataFrame([row for row in rows if row["dataset"] == "Real-world" and row["model"] != "Ranker"])
    labels = real["model"].tolist()
    values = real["f1"].tolist()
    return save_bar_chart(
        "resume_realworld_f1_comparison.png",
        "Real-world Classifier F1 Comparison",
        labels,
        values,
        "F1 (%)",
        ["#2563eb", "#16a34a"],
        (0, 100),
    )


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_model_rows()
    outputs = [
        plot_model_metric_comparison(rows),
        plot_ranker_comparison(rows),
        plot_dataset_profile(),
        plot_bias_audit(),
        plot_realworld_summary(rows),
    ]
    parser_chart = plot_parser_robustness()
    if parser_chart:
        outputs.append(parser_chart)

    manifest = {
        "generated_charts": [path.name for path in outputs],
        "generated_at_note": "Charts are derived from existing canonical and resume_realworld artifacts.",
    }
    (CHARTS_DIR / "realworld_comparison_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
