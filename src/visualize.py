import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx


def plot_metrics(rules: pd.DataFrame, output_path: str = "output/metrics.png") -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Association Rules — Key Metrics", fontsize=14)

    axes[0].hist(rules["support"], bins=10, color="steelblue", edgecolor="white")
    axes[0].set_title("Support Distribution")
    axes[0].set_xlabel("Support")

    axes[1].hist(rules["confidence"], bins=10, color="seagreen", edgecolor="white")
    axes[1].set_title("Confidence Distribution")
    axes[1].set_xlabel("Confidence")

    axes[2].hist(rules["lift"], bins=10, color="tomato", edgecolor="white")
    axes[2].set_title("Lift Distribution")
    axes[2].set_xlabel("Lift")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Metrics chart saved: {output_path}")


def plot_network(rules: pd.DataFrame, top_n: int = 20, output_path: str = "output/network.png") -> None:
    top = rules.head(top_n)
    G = nx.DiGraph()

    for _, row in top.iterrows():
        antecedent = row["antecedents"] if isinstance(row["antecedents"], str) else ", ".join(sorted(row["antecedents"]))
        consequent = row["consequents"] if isinstance(row["consequents"], str) else ", ".join(sorted(row["consequents"]))
        G.add_edge(antecedent, consequent, weight=round(row["lift"], 2))

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, seed=42)
    weights = [G[u][v]["weight"] for u, v in G.edges()]
    nx.draw_networkx_nodes(G, pos, node_size=1800, node_color="steelblue", alpha=0.85)
    nx.draw_networkx_labels(G, pos, font_size=8, font_color="white")
    nx.draw_networkx_edges(G, pos, width=[w * 0.5 for w in weights], edge_color="gray", arrows=True, arrowsize=15)
    edge_labels = {(u, v): f"{d['weight']}" for u, v, d in G.edges(data=True)}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7)
    plt.title("Association Rules Network (sized by Lift)", fontsize=13)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Network graph saved: {output_path}")


def plot_heatmap(rules: pd.DataFrame, output_path: str = "output/heatmap.png") -> None:
    rules = rules.copy()
    rules["antecedents_str"] = rules["antecedents"].apply(lambda x: x if isinstance(x, str) else ", ".join(sorted(x)))
    rules["consequents_str"] = rules["consequents"].apply(lambda x: x if isinstance(x, str) else ", ".join(sorted(x)))
    pivot = rules.pivot_table(index="antecedents_str", columns="consequents_str", values="lift", aggfunc="max")

    plt.figure(figsize=(10, 6))
    im = plt.imshow(pivot.values, aspect="auto", cmap="YlOrRd")
    plt.colorbar(im, label="Lift")
    plt.xticks(range(len(pivot.columns)), pivot.columns, rotation=45, ha="right", fontsize=8)
    plt.yticks(range(len(pivot.index)), pivot.index, fontsize=8)
    plt.title("Lift Heatmap: Antecedents vs Consequents", fontsize=13)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Heatmap saved: {output_path}")
