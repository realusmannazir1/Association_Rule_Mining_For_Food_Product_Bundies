"""Shared analysis pipeline used by the desktop app and command line."""

from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.apriori import encode_transactions, load_transactions, mine_rules
from src.visualize import plot_heatmap, plot_metrics, plot_network


def run_pipeline(data_path, min_support=0.05, min_confidence=0.30, min_lift=1.0, output_dir="output", progress=None):
    """Prepare data, mine with both algorithms, save results and charts."""
    def report(message):
        if progress:
            progress(message)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report("Loading and preparing transactions...")
    transactions = load_transactions(data_path)
    encoded = encode_transactions(transactions)
    n = len(transactions)
    counts = encoded.sum().sort_values(ascending=False)
    summary = {
        "dataset_file": str(data_path), "transactions": n,
        "distinct_items": int(encoded.shape[1]),
        "empty_transactions_removed": 0,
        "average_basket_size": round(sum(map(len, transactions)) / n, 3),
        "min_support": min_support, "min_confidence": min_confidence, "min_lift": min_lift,
    }
    (out / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    counts.rename("basket_count").to_csv(out / "item_frequencies.csv", header=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    counts.head(15).sort_values().plot.barh(ax=ax, color="#2c7a7b")
    ax.set(title="15 Most Frequent Products", xlabel="Number of baskets", ylabel="Product")
    fig.tight_layout(); fig.savefig(out / "eda_top_items.png", dpi=160); plt.close(fig)
    sizes = pd.Series([len(set(t)) for t in transactions])
    fig, ax = plt.subplots(figsize=(8, 4))
    sizes.value_counts().sort_index().plot.bar(ax=ax, color="#d69e2e")
    ax.set(title="Basket Size Distribution", xlabel="Distinct products per basket", ylabel="Number of baskets")
    fig.tight_layout(); fig.savefig(out / "eda_basket_sizes.png", dpi=160); plt.close(fig)

    comparison, all_rules = [], []
    for algorithm in ("apriori", "fpgrowth"):
        report(f"Mining rules with {algorithm.replace('fpgrowth', 'FP-Growth')}...")
        start = time.perf_counter()
        itemsets, rules = mine_rules(encoded, algorithm, min_support, min_confidence, min_lift)
        elapsed = time.perf_counter() - start
        itemsets = itemsets.copy()
        if not itemsets.empty:
            itemsets["itemsets"] = itemsets["itemsets"].map(lambda x: ", ".join(sorted(x)))
        itemsets.to_csv(out / f"{algorithm}_frequent_itemsets.csv", index=False)
        rules.to_csv(out / f"{algorithm}_rules.csv", index=False)
        comparison.append({"algorithm": algorithm, "frequent_itemsets": len(itemsets), "rules": len(rules), "runtime_seconds": round(elapsed, 6)})
        if not rules.empty:
            tagged = rules.copy(); tagged.insert(0, "algorithm", algorithm); all_rules.append(tagged)
    pd.DataFrame(comparison).to_csv(out / "algorithm_comparison.csv", index=False)
    combined = pd.concat(all_rules, ignore_index=True) if all_rules else pd.DataFrame()
    if not combined.empty:
        combined.sort_values(["lift", "support", "confidence"], ascending=False).to_csv(out / "ranked_rules.csv", index=False)
        unique = combined.drop_duplicates(["antecedents", "consequents"])
        plot_metrics(combined, output_path=str(out / "metrics.png"))
        plot_network(unique, output_path=str(out / "network.png"))
        plot_heatmap(unique, output_path=str(out / "heatmap.png"))
    report("Analysis complete.")
    return {"summary": summary, "comparison": comparison, "rules": combined, "output_dir": out}
