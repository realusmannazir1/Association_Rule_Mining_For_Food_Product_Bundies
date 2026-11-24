"""Run the food basket association-mining comparison."""
import argparse
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.apriori import encode_transactions, load_transactions, mine_rules
from src.visualize import plot_heatmap, plot_metrics, plot_network


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Apriori and FP-Growth for food bundles")
    parser.add_argument("--data", default="data/groceries.csv", help="CSV: wide baskets or basket_id,product_name rows")
    parser.add_argument("--support", type=float, default=0.10)
    parser.add_argument("--confidence", type=float, default=0.30)
    parser.add_argument("--lift", type=float, default=1.0)
    parser.add_argument("--out", default="output")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    transactions = load_transactions(args.data)
    encoded = encode_transactions(transactions)
    n = len(transactions)
    item_counts = encoded.sum().sort_values(ascending=False)
    summary = {
        "dataset_file": str(args.data), "transactions": n,
        "distinct_items": int(encoded.shape[1]),
        "empty_transactions_removed": 0,
        "average_basket_size": round(sum(map(len, transactions)) / n, 3),
        "duplicate_items_within_basket_removed_by_encoding": True,
        "min_support": args.support, "min_confidence": args.confidence, "min_lift": args.lift,
    }
    (out / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    item_counts.rename("basket_count").to_csv(out / "item_frequencies.csv", header=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    item_counts.head(15).sort_values().plot.barh(ax=ax, color="#2c7a7b")
    ax.set(title="15 Most Frequent Products", xlabel="Number of baskets", ylabel="Product")
    fig.tight_layout(); fig.savefig(out / "eda_top_items.png", dpi=160); plt.close(fig)
    basket_sizes = pd.Series([len(set(t)) for t in transactions])
    fig, ax = plt.subplots(figsize=(8, 4))
    basket_sizes.value_counts().sort_index().plot.bar(ax=ax, color="#d69e2e")
    ax.set(title="Basket Size Distribution", xlabel="Distinct products per basket", ylabel="Number of baskets")
    fig.tight_layout(); fig.savefig(out / "eda_basket_sizes.png", dpi=160); plt.close(fig)

    comparison = []
    all_rules = []
    for algorithm in ("apriori", "fpgrowth"):
        start = time.perf_counter()
        itemsets, rules = mine_rules(encoded, algorithm, args.support, args.confidence, args.lift)
        elapsed = time.perf_counter() - start
        itemsets = itemsets.copy()
        if not itemsets.empty:
            itemsets["itemsets"] = itemsets["itemsets"].map(lambda x: ", ".join(sorted(x)))
            itemsets.to_csv(out / f"{algorithm}_frequent_itemsets.csv", index=False)
        rules.to_csv(out / f"{algorithm}_rules.csv", index=False)
        comparison.append({"algorithm": algorithm, "frequent_itemsets": len(itemsets), "rules": len(rules), "runtime_seconds": round(elapsed, 6)})
        if not rules.empty:
            tagged = rules.copy(); tagged.insert(0, "algorithm", algorithm); all_rules.append(tagged)
        print(f"{algorithm}: {len(itemsets)} frequent itemsets, {len(rules)} rules, {elapsed:.6f}s")

    pd.DataFrame(comparison).to_csv(out / "algorithm_comparison.csv", index=False)
    combined = pd.concat(all_rules, ignore_index=True) if all_rules else pd.DataFrame()
    if not combined.empty:
        # Rules can be ranked by lift, but also retain support/confidence so prevalence is visible.
        combined = combined.sort_values(["lift", "support", "confidence"], ascending=False)
        combined.to_csv(out / "ranked_rules.csv", index=False)
        plot_metrics(combined)
        plot_network(combined.drop_duplicates(["antecedents", "consequents"]), output_path=str(out / "network.png"))
        plot_heatmap(combined.drop_duplicates(["antecedents", "consequents"]), output_path=str(out / "heatmap.png"))
    print(f"\nTransactions: {n}; distinct products: {encoded.shape[1]}; average basket size: {summary['average_basket_size']}")
    print(f"Results written to {out.resolve()}")


if __name__ == "__main__":
    main()
