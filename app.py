"""Small desktop application for the DS-A38 basket analysis project."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd
from PIL import Image, ImageTk

from src.pipeline import run_pipeline


ROOT = Path(__file__).resolve().parent
BG = "#f3f6f8"
NAVY = "#102b3f"
TEAL = "#0f766e"
TEXT = "#183247"
MUTED = "#687b8c"
WHITE = "#ffffff"


class AssociationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Basket Insights | Association Rule Mining")
        self.geometry("1220x820")
        self.state("normal")
        self.minsize(1000, 700)
        self.configure(bg=BG)
        self.lift()
        self.focus_force()
        self.data_path = tk.StringVar(value=str(ROOT / "data" / "groceries.csv"))
        self.support = tk.StringVar(value="0.05")
        self.confidence = tk.StringVar(value="0.30")
        self.lift = tk.StringVar(value="1.0")
        self.status = tk.StringVar(value="Ready to analyze")
        self.events: queue.Queue = queue.Queue()
        self.chart_images = []
        self._styles()
        self._build()
        self.after(150, self._poll_events)
        self._load_existing()

    def _styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), background="#e5edf1", foreground=TEXT, font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", WHITE)], foreground=[("selected", TEAL)])
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=29, background=WHITE, fieldbackground=WHITE, foreground=TEXT, borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#eaf0f3", foreground=TEXT, relief="flat", padding=8)
        style.map("Treeview", background=[("selected", "#cdebe6")], foreground=[("selected", TEXT)])
        style.configure("TEntry", padding=8, fieldbackground=WHITE)
        style.configure("TButton", padding=(12, 8), font=("Segoe UI", 9, "bold"))

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        side = tk.Frame(self, bg=NAVY, width=226)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        tk.Label(side, text="BASKET\nINSIGHTS", bg=NAVY, fg=WHITE, font=("Segoe UI", 19, "bold"), justify="left").pack(anchor="w", padx=23, pady=(30, 6))
        tk.Label(side, text="ASSOCIATION RULE MINING", bg=NAVY, fg="#91b8c8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24, pady=(0, 30))
        tk.Frame(side, height=1, bg="#2b4a5d").pack(fill="x", padx=20, pady=5)
        tk.Label(side, text="DS-A38  •  FINAL PROJECT", bg=NAVY, fg="#bdced8", font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(17, 5))
        tk.Label(side, text="Apriori  +  FP-Growth", bg=NAVY, fg=WHITE, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=24)
        tk.Label(side, text="Compare frequent patterns and\ninspect bundle hypotheses.", bg=NAVY, fg="#bdced8", font=("Segoe UI", 9), justify="left").pack(anchor="w", padx=24, pady=(8, 26))
        tk.Label(side, text="STUDENT", bg=NAVY, fg="#91b8c8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24, pady=(8, 4))
        tk.Label(side, text="Muhammad Usman Nazir", bg=NAVY, fg=WHITE, font=("Segoe UI", 9)).pack(anchor="w", padx=24)
        tk.Label(side, text="24PWDSC0178", bg=NAVY, fg="#bdced8", font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(3, 20))
        tk.Frame(side, bg=NAVY).pack(fill="both", expand=True)
        tk.Label(side, text="Results are saved locally\nin the output folder.", bg=NAVY, fg="#91a9b8", font=("Segoe UI", 8), justify="left").pack(anchor="w", padx=24, pady=20)

        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)
        top = tk.Frame(main, bg=BG)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        tk.Label(top, text="Grocery basket analysis", bg=BG, fg=TEXT, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(top, text="Discover which products appear together and compare the mining methods.", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))

        controls = tk.Frame(main, bg=WHITE, highlightbackground="#dde6eb", highlightthickness=1)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        controls.grid_columnconfigure(1, weight=1)
        tk.Label(controls, text="DATASET", bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=(16, 8), pady=(13, 4))
        self.path_entry = ttk.Entry(controls, textvariable=self.data_path)
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=(10, 4))
        ttk.Button(controls, text="Browse…", command=self._browse).grid(row=0, column=2, padx=(5, 16), pady=(10, 4))
        tk.Label(controls, text="RULE THRESHOLDS", bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(row=1, column=0, sticky="w", padx=(16, 8), pady=(7, 13))
        fields = tk.Frame(controls, bg=WHITE)
        fields.grid(row=1, column=1, columnspan=2, sticky="ew", padx=4, pady=(4, 10))
        self._threshold_field(fields, "Support", self.support, 0)
        self._threshold_field(fields, "Confidence", self.confidence, 1)
        self._threshold_field(fields, "Lift", self.lift, 2)
        self.run_button = tk.Button(controls, text="▶   Run analysis", bg=TEAL, fg=WHITE, activebackground="#0b625c", activeforeground=WHITE, relief="flat", font=("Segoe UI", 10, "bold"), padx=16, pady=9, command=self._run)
        self.run_button.grid(row=1, column=3, padx=14, pady=(4, 10))

        self.summary_row = tk.Frame(main, bg=BG)
        self.summary_row.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        self.summary_row.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.cards = {}
        for i, (key, label) in enumerate((("transactions", "BASKETS"), ("distinct_items", "PRODUCTS"), ("itemsets", "FREQUENT ITEMSETS"), ("rules", "RULES FOUND"))):
            card = tk.Frame(self.summary_row, bg=WHITE, highlightbackground="#dde6eb", highlightthickness=1)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            tk.Label(card, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
            value = tk.Label(card, text="—", bg=WHITE, fg=TEXT, font=("Segoe UI", 20, "bold"))
            value.pack(anchor="w", padx=14, pady=(0, 10))
            self.cards[key] = value

        self.tabs = ttk.Notebook(main)
        self.tabs.grid(row=3, column=0, sticky="nsew")
        self.rules_tab = tk.Frame(self.tabs, bg=WHITE)
        self.compare_tab = tk.Frame(self.tabs, bg=WHITE)
        self.charts_tab = tk.Frame(self.tabs, bg=WHITE)
        self.tabs.add(self.rules_tab, text="Ranked rules")
        self.tabs.add(self.compare_tab, text="Algorithm comparison")
        self.tabs.add(self.charts_tab, text="Charts")
        self._build_rules()
        self._build_comparison()
        self._build_charts()
        self.tabs.select(self.rules_tab)

        bottom = tk.Frame(main, bg=BG)
        bottom.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.status_label = tk.Label(bottom, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.status_label.pack(side="left")
        tk.Button(bottom, text="Open results folder", bg=BG, fg=TEAL, activebackground=BG, relief="flat", font=("Segoe UI", 9, "bold"), command=self._open_output).pack(side="right")

    def _threshold_field(self, parent, label, variable, col):
        wrap = tk.Frame(parent, bg=WHITE)
        wrap.grid(row=0, column=col, sticky="w", padx=(0, 22))
        tk.Label(wrap, text=label, bg=WHITE, fg=TEXT, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))
        entry = ttk.Entry(wrap, textvariable=variable, width=10)
        entry.pack(anchor="w")

    def _build_rules(self):
        title = tk.Frame(self.rules_tab, bg=WHITE)
        title.pack(fill="x", padx=16, pady=(15, 8))
        tk.Label(title, text="Rules ranked by lift", bg=WHITE, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(title, text="Review support and confidence too; lift shows association beyond the consequent’s baseline popularity.", bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        table = tk.Frame(self.rules_tab, bg=WHITE)
        table.pack(fill="both", expand=True, padx=16, pady=(5, 16))
        cols = ("algorithm", "antecedents", "consequents", "support", "confidence", "lift")
        self.rule_tree = ttk.Treeview(table, columns=cols, show="headings", height=12)
        widths = (105, 185, 185, 85, 105, 75)
        labels = ("Method", "If basket contains", "Likely also contains", "Support", "Confidence", "Lift")
        for col, label, width in zip(cols, labels, widths):
            self.rule_tree.heading(col, text=label)
            self.rule_tree.column(col, width=width, anchor="w" if col in ("algorithm", "antecedents", "consequents") else "center")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.rule_tree.yview)
        self.rule_tree.configure(yscrollcommand=scroll.set)
        self.rule_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _build_comparison(self):
        tk.Label(self.compare_tab, text="Same thresholds, two mining strategies", bg=WHITE, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(self.compare_tab, text="Both methods should return matching frequent itemsets. Runtime depends on dataset size and shape.", bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 14))
        cols = ("algorithm", "frequent_itemsets", "rules", "runtime_seconds")
        self.compare_tree = ttk.Treeview(self.compare_tab, columns=cols, show="headings", height=5)
        for col, label, width in zip(cols, ("Algorithm", "Frequent itemsets", "Rules", "Runtime (seconds)"), (190, 200, 120, 180)):
            self.compare_tree.heading(col, text=label); self.compare_tree.column(col, width=width, anchor="center")
        self.compare_tree.pack(anchor="w", padx=18, fill="x")
        self.compare_note = tk.Label(self.compare_tab, text="Run the analysis to compare Apriori and FP-Growth.", bg=WHITE, fg=MUTED, font=("Segoe UI", 9), wraplength=760, justify="left")
        self.compare_note.pack(anchor="w", padx=18, pady=18)

    def _build_charts(self):
        shell = tk.Frame(self.charts_tab, bg=WHITE)
        shell.pack(fill="both", expand=True)
        canvas = tk.Canvas(shell, bg=WHITE, highlightthickness=0)
        scroll = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.chart_frame = tk.Frame(canvas, bg=WHITE)
        self.chart_window = canvas.create_window((0, 0), window=self.chart_frame, anchor="nw")
        self.chart_canvas = canvas
        self.chart_frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(self.chart_window, width=event.width))
        tk.Label(self.chart_frame, text="Visual summaries will appear here after analysis.", bg=WHITE, fg=MUTED, font=("Segoe UI", 10)).grid(row=0, column=0, padx=30, pady=40)

    def _browse(self):
        chosen = filedialog.askopenfilename(title="Choose a basket data file", initialdir=ROOT / "data", filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))
        if chosen:
            self.data_path.set(chosen)

    def _run(self):
        try:
            support, confidence, lift = float(self.support.get()), float(self.confidence.get()), float(self.lift.get())
            if not (0 < support <= 1 and 0 <= confidence <= 1 and lift >= 0):
                raise ValueError("Support and confidence must be between 0 and 1. Lift must be zero or greater.")
            if not Path(self.data_path.get()).is_file():
                raise ValueError("Choose an existing CSV dataset first.")
        except ValueError as exc:
            messagebox.showerror("Check the analysis settings", str(exc), parent=self)
            return
        self.run_button.configure(state="disabled", text="Running…")
        self.status.set("Preparing analysis…")
        thread = threading.Thread(target=self._worker, args=(support, confidence, lift), daemon=True)
        thread.start()

    def _worker(self, support, confidence, lift):
        try:
            result = run_pipeline(self.data_path.get(), support, confidence, lift, ROOT / "output", progress=lambda msg: self.events.put(("status", msg)))
            self.events.put(("success", result))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status.set(payload)
                elif kind == "success":
                    self._show_results(payload)
                    self.run_button.configure(state="normal", text="▶   Run analysis")
                elif kind == "error":
                    self.status.set("Analysis could not be completed")
                    self.run_button.configure(state="normal", text="▶   Run analysis")
                    messagebox.showerror("Analysis error", payload, parent=self)
        except queue.Empty:
            pass
        self.after(150, self._poll_events)

    def _show_results(self, result):
        summary = result["summary"]
        comparison = result["comparison"]
        rules = result["rules"]
        self.cards["transactions"].configure(text=f"{summary['transactions']:,}")
        self.cards["distinct_items"].configure(text=f"{summary['distinct_items']:,}")
        self.cards["itemsets"].configure(text=f"{comparison[0]['frequent_itemsets']:,}")
        unique_rules = rules.drop_duplicates(["antecedents", "consequents"]) if not rules.empty else rules
        self.cards["rules"].configure(text=f"{len(unique_rules):,}")
        for tree in (self.rule_tree, self.compare_tree):
            tree.delete(*tree.get_children())
        if not unique_rules.empty:
            for row in unique_rules.sort_values(["lift", "support"], ascending=False).itertuples():
                sources = rules.loc[(rules["antecedents"] == row.antecedents) & (rules["consequents"] == row.consequents), "algorithm"].unique()
                method = "Both" if len(sources) > 1 else ("FP-Growth" if sources[0] == "fpgrowth" else "Apriori")
                self.rule_tree.insert("", "end", values=(method, row.antecedents, row.consequents, f"{row.support:.3f}", f"{row.confidence:.3f}", f"{row.lift:.3f}"))
        for row in comparison:
            name = "FP-Growth" if row["algorithm"] == "fpgrowth" else "Apriori"
            self.compare_tree.insert("", "end", values=(name, row["frequent_itemsets"], row["rules"], f"{row['runtime_seconds']:.6f}"))
        self.compare_note.configure(text=f"Analyzed {summary['transactions']:,} baskets with {summary['distinct_items']:,} products. Average basket size: {summary['average_basket_size']}. Treat rules as co-purchase patterns, not proof that one product causes another purchase.")
        self._load_charts()
        self.status.set(f"Complete · results saved to {result['output_dir']}")

    def _load_charts(self):
        for child in self.chart_frame.winfo_children():
            child.destroy()
        self.chart_images.clear()
        files = (("Product frequency", "eda_top_items.png"), ("Basket sizes", "eda_basket_sizes.png"), ("Rule metrics", "metrics.png"), ("Rule network", "network.png"), ("Lift heatmap", "heatmap.png"))
        for i, (title, filename) in enumerate(files):
            path = ROOT / "output" / filename
            if not path.exists():
                continue
            image = Image.open(path).convert("RGB")
            image.thumbnail((445, 285))
            photo = ImageTk.PhotoImage(image)
            self.chart_images.append(photo)
            card = tk.Frame(self.chart_frame, bg="#f7f9fa", highlightbackground="#e0e8ed", highlightthickness=1)
            card.grid(row=i // 2, column=i % 2, sticky="nw", padx=8, pady=8)
            tk.Label(card, text=title, bg="#f7f9fa", fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
            tk.Label(card, image=photo, bg="#f7f9fa").pack(padx=7, pady=(0, 7))

    def _load_existing(self):
        summary_path = ROOT / "output" / "dataset_summary.json"
        comparison_path = ROOT / "output" / "algorithm_comparison.csv"
        rules_path = ROOT / "output" / "ranked_rules.csv"
        if summary_path.exists() and comparison_path.exists() and rules_path.exists():
            try:
                import json
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                comparison = pd.read_csv(comparison_path).to_dict("records")
                rules = pd.read_csv(rules_path)
                self._show_results({"summary": summary, "comparison": comparison, "rules": rules, "output_dir": ROOT / "output"})
                self.status.set("Showing the latest saved analysis")
            except Exception:
                pass

    def _open_output(self):
        import os
        os.startfile(ROOT / "output")


if __name__ == "__main__":
    AssociationApp().mainloop()
