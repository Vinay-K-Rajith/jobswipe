import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
CHARTS_DIR = os.path.join(MODEL_DIR, "charts")


def main():
    with open(os.path.join(MODEL_DIR, "epsilon_sweep_results.json")) as f:
        sweep = json.load(f)
    sweep.sort(key=lambda row: row["eps"])

    eps_vals = [row["eps"] for row in sweep]
    acc_vals = [row["accuracy"] for row in sweep]
    bias_vals = [row["gender_parity_gap"] for row in sweep]
    f1_vals = [row["f1"] for row in sweep]

    os.makedirs(CHARTS_DIR, exist_ok=True)
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.set_xlabel("Fairlearn Epsilon")
    ax1.set_ylabel("Accuracy (%)", color="steelblue")
    l1, = ax1.plot(eps_vals, acc_vals, "o-", color="steelblue", label="Accuracy (%)", linewidth=2)
    l2, = ax1.plot(eps_vals, [f1 * 100 for f1 in f1_vals], "s--", color="steelblue", alpha=0.6, label="F1 x 100", linewidth=1.5)
    ax1.tick_params(axis="y", labelcolor="steelblue")

    ax2 = ax1.twinx()
    ax2.set_ylabel("Gender Parity Gap (%)", color="firebrick")
    l3, = ax2.plot(eps_vals, bias_vals, "^-", color="firebrick", label="Gender Parity Gap (%)", linewidth=2)
    ax2.axhline(y=10, color="red", linestyle=":", alpha=0.5, linewidth=1.5)
    ax2.tick_params(axis="y", labelcolor="firebrick")

    champion_idx = next((i for i, row in enumerate(sweep) if abs(row["eps"] - 0.01) < 0.001), None)
    if champion_idx is not None:
        ax1.axvline(x=eps_vals[champion_idx], color="gold", linestyle="--", alpha=0.7)
        ax1.annotate(
            "Champion (eps=0.01)",
            xy=(eps_vals[champion_idx], acc_vals[champion_idx]),
            xytext=(eps_vals[champion_idx] + 0.003, acc_vals[champion_idx] - 1),
            fontsize=9,
            color="darkgoldenrod",
        )

    lines = [l1, l2, l3]
    ax1.legend(lines, [line.get_label() for line in lines], loc="center right")
    plt.title("Fairlearn Epsilon Sensitivity: Accuracy vs Gender Parity Gap")
    plt.tight_layout()
    out = os.path.join(CHARTS_DIR, "epsilon_sweep.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
