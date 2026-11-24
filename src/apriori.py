"""Transaction preparation and association-rule mining helpers."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules, fpgrowth
from mlxtend.preprocessing import TransactionEncoder


def load_transactions(filepath: str | Path) -> list[list[str]]:
    """Load either transaction_id/items rows or a normalized basket,item CSV.

    For the supplied wide sample, each row is a basket and every field after
    transaction_id is an item. For Dunnhumby-style data, pass a two-column
    file with basket_id and product_name (one row per basket-item pair).
    """
    path = Path(filepath)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        fields = {name.strip().lower(): name for name in reader.fieldnames}
        rows = list(reader)
    basket_col = next((fields[k] for k in ("basket_id", "transaction_id", "basket", "order_id") if k in fields), None)

    # The starter example has unquoted comma-separated products despite a
    # two-column header. DictReader exposes these overflow fields under None.
    if rows and any(None in row for row in rows):
        transactions = []
        for row in rows:
            items = []
            for key, value in row.items():
                if key is None:
                    values = value if isinstance(value, list) else [value]
                elif key == basket_col:
                    continue
                else:
                    values = [value]
                for cell in values:
                    if cell:
                        items.extend(part.strip() for part in str(cell).split(",") if part.strip())
            if items:
                transactions.append(items)
        return transactions

    item_col = next((fields[k] for k in ("product_name", "item", "product", "item_name", "items") if k in fields), None)
    wide_item_list = bool(item_col and any("," in (row.get(item_col) or "") for row in rows))
    if basket_col and item_col and basket_col != item_col and not wide_item_list:
        baskets: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            basket = (row.get(basket_col) or "").strip()
            item = (row.get(item_col) or "").strip()
            if basket and item:
                baskets[basket].add(item)
        transactions = [sorted(items) for items in baskets.values() if items]
    else:
        transactions = []
        for row in rows:
            items = []
            for key, value in row.items():
                if key == basket_col or not value or not str(value).strip():
                    continue
                # Some wide samples store comma-delimited basket contents in one field.
                items.extend(part.strip() for part in str(value).split(",") if part.strip())
            if items:
                transactions.append(items)
    if not transactions:
        raise ValueError("No non-empty transactions found. Expected wide rows or basket_id,product_name columns.")
    return transactions


def encode_transactions(transactions: list[list[str]]) -> pd.DataFrame:
    encoder = TransactionEncoder()
    encoded = encoder.fit_transform(transactions)
    return pd.DataFrame(encoded, columns=encoder.columns_, dtype=bool)


def mine_rules(
    encoded: pd.DataFrame,
    algorithm: str = "apriori",
    min_support: float = 0.1,
    min_confidence: float = 0.3,
    min_lift: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (frequent itemsets, ranked rules) for Apriori or FP-Growth."""
    if algorithm not in {"apriori", "fpgrowth"}:
        raise ValueError("algorithm must be 'apriori' or 'fpgrowth'")
    miner = apriori if algorithm == "apriori" else fpgrowth
    itemsets = miner(encoded, min_support=min_support, use_colnames=True)
    if itemsets.empty:
        return itemsets, pd.DataFrame()
    rules = association_rules(itemsets, metric="confidence", min_threshold=min_confidence)
    rules = rules.loc[rules["lift"] >= min_lift].copy()
    rules["antecedents"] = rules["antecedents"].map(lambda x: ", ".join(sorted(x)))
    rules["consequents"] = rules["consequents"].map(lambda x: ", ".join(sorted(x)))
    rules = rules.sort_values(["lift", "support", "confidence"], ascending=False).reset_index(drop=True)
    return itemsets, rules
