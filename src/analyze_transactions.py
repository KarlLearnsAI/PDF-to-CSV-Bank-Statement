import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def format_k(x):
    """Format 1234 → '1.2k', 950 → '950'"""
    if abs(x) >= 1000:
        return f"{x/1000:.1f}k"
    return f"{x:.0f}"

def main():
    df = pd.read_csv("data/processed_transactions.csv", parse_dates=["Date"])

    # derive a month period
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()

    # aggregate
    summary = df.groupby("Month").agg(
        Income  = ("Cash In", "sum"),
        Outcome = ("Cash Out", "sum")
    )
    summary["Net"] = summary["Income"] - summary["Outcome"]

    # plot
    months = summary.index.to_pydatetime()
    x = np.arange(len(months))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width, summary["Income"],   width)
    bars2 = ax.bar(x,       summary["Outcome"],  width)
    bars3 = ax.bar(x + width, summary["Net"],     width)

    # x-axis labels
    ax.set_xticks(x)
    ax.set_xticklabels([m.strftime("%b %Y") for m in months], rotation=45, ha="right")
    ax.set_ylabel("Amount (€)")
    ax.set_title("Monthly Income, Outcome, and Net")

    # annotate each bar
    for bar in [*bars1, *bars2, *bars3]:
        h = bar.get_height()
        label = format_k(h)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + (0.01 * summary.values.max()),
            label,
            ha="center",
            va="bottom",
            fontsize=9
        )
    plt.tight_layout()
    plt.show()
    print("Analysis complete")

if __name__ == "__main__":
    main()