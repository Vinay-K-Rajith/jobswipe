import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
CHARTS_DIR = os.path.join(MODEL_DIR, "charts")


def main():
    with open(os.path.join(MODEL_DIR, "comprehensive_search_results.json")) as f:
        results = json.load(f)

    x = [row["Accuracy"] for row in results]
    y = [row["Gender_Parity_Gap"] for row in results]
    names = [row["Approach"] for row in results]

    pareto = []
    for i in range(len(results)):
        dominated = any(
            j != i and x[j] >= x[i] and y[j] <= y[i] and (x[j] > x[i] or y[j] < y[i])
            for j in range(len(results))
        )
        if not dominated:
            pareto.append(i)

    pareto_sorted = sorted(pareto, key=lambda i: x[i])
    pareto_x_vals = [x[i] for i in pareto_sorted]
    pareto_y_vals = [y[i] for i in pareto_sorted]

    os.makedirs(CHARTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.scatter(x, y, c="lightsteelblue", s=80, zorder=3, edgecolors="steelblue", linewidths=0.8)
    for i, name in enumerate(names):
        ax.annotate(
            name.replace("_", "\n"),
            (x[i], y[i]),
            xytext=(x[i] + 0.03, y[i] + (0.15 if i % 2 == 0 else -0.35)),
            fontsize=7,
            ha="left",
            color="dimgray",
        )

    ax.plot(pareto_x_vals, pareto_y_vals, "r--", linewidth=1.8, label="Pareto frontier", zorder=4)
    if "Fairlearn_LightGBM" in names:
        champ_idx = names.index("Fairlearn_LightGBM")
        ax.scatter(
            [x[champ_idx]],
            [y[champ_idx]],
            c="gold",
            s=250,
            marker="*",
            zorder=5,
            edgecolors="darkorange",
            linewidths=1.2,
            label="Champion (Fairlearn LightGBM)",
        )

    ax.axhline(y=10, color="red", linestyle=":", alpha=0.5, linewidth=1.5, label="10% fairness threshold")
    ax.set_xlabel("Accuracy (%)")
    ax.set_ylabel("Gender Parity Gap (%)")
    ax.set_title("Accuracy-Fairness Pareto Frontier")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    out = os.path.join(CHARTS_DIR, "pareto_frontier.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
