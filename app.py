"""Basket Insights: a native desktop dashboard for association-rule mining."""

from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from src.apriori import encode_transactions, load_transactions
from src.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
C = {
    "page": "#f4f7fb", "surface": "#ffffff", "nav": "#12233f", "nav2": "#192e50",
    "ink": "#172b4d", "muted": "#718096", "line": "#e4eaf2", "teal": "#14877e",
    "teal_light": "#e4f5f2", "blue": "#3974d8", "blue_light": "#edf3ff",
    "orange": "#d68136", "orange_light": "#fff3e5", "red": "#c64b5e",
    "green": "#21856b", "purple": "#7658ca", "white": "#ffffff",
}
FONT = "Segoe UI"


class BasketInsights(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Basket Insights | Retail Analytics")
        self.geometry("1480x940")
        self.minsize(1120, 760)
        self.state("normal")
        self.configure(bg=C["page"])
        self.lift()
        self.focus_force()

        self.events: queue.Queue = queue.Queue()
        self.sidebar_open = True
        self.sidebar_width = 252
        self.nav_headers = []
        self.nav_groups = {}
        self.active_page = "Overview"
        self.nav_buttons = {}
        self.page_frames = {}
        self.rule_data = pd.DataFrame()
        self.itemset_data = pd.DataFrame()
        self.frequency_data = pd.Series(dtype="int64")
        self.transactions = []
        self.comparison = []
        self.summary = {}
        self.rule_page = 0
        self.page_size = 25
        self.sort_column = "lift"
        self.sort_reverse = True
        self.item_sort_column = "support"
        self.item_sort_reverse = True
        self.visible_rule_columns = ["algorithm", "antecedents", "consequents", "support", "confidence", "lift"]
        self.run_buttons = []

        self.data_path = tk.StringVar(value=str(ROOT / "data" / "groceries.csv"))
        self.min_support = tk.StringVar(value="0.05")
        self.min_confidence = tk.StringVar(value="0.30")
        self.min_lift = tk.StringVar(value="1.0")
        self.global_search = tk.StringVar()
        self.rule_search = tk.StringVar()
        self.rule_min_lift = tk.StringVar(value="0.0")
        self.rule_algorithm = tk.StringVar(value="All methods")
        self.chart_kind = tk.StringVar(value="Bar")
        self.chart_metric = tk.StringVar(value="Product frequency")
        self.status = tk.StringVar(value="Ready · select a dataset and run analysis")
        self.period = tk.StringVar(value="All available baskets")

        self._style()
        self._build_shell()
        self._load_existing()
        self.after(120, self._poll_events)
        self.bind("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.bind("<Control-r>", lambda _e: self._run_analysis())

    # ------------------------------------------------------------------ theme
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview", background=C["surface"], fieldbackground=C["surface"], foreground=C["ink"],
                    borderwidth=0, rowheight=32, font=(FONT, 9))
        s.configure("Treeview.Heading", background="#eef2f7", foreground="#52647d", relief="flat",
                    font=(FONT, 9, "bold"), padding=(9, 9))
        s.map("Treeview", background=[("selected", "#dceafe")], foreground=[("selected", C["ink"])])
        s.configure("TCombobox", padding=(9, 7), fieldbackground=C["surface"], background=C["surface"], foreground=C["ink"])
        s.configure("TEntry", padding=(9, 8), fieldbackground=C["surface"], foreground=C["ink"])
        s.configure("TScrollbar", background="#dae2ec", troughcolor=C["page"], bordercolor=C["page"], arrowsize=12)

    # --------------------------------------------------------------- app shell
    def _build_shell(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.sidebar = tk.Frame(self, bg=C["nav"], width=self.sidebar_width)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        self.workspace = tk.Frame(self, bg=C["page"])
        self.workspace.grid(row=0, column=1, sticky="nsew")
        self.workspace.grid_rowconfigure(1, weight=1)
        self.workspace.grid_columnconfigure(0, weight=1)
        self._build_header()
        self.page_view = tk.Frame(self.workspace, bg=C["page"])
        self.page_view.grid(row=1, column=0, sticky="nsew", padx=(28, 12), pady=(18, 12))
        self.page_view.grid_rowconfigure(0, weight=1)
        self.page_view.grid_columnconfigure(0, weight=1)
        self.page_canvas = tk.Canvas(self.page_view, bg=C["page"], highlightthickness=0, bd=0)
        self.page_canvas.grid(row=0, column=0, sticky="nsew")
        self.page_scrollbar = ttk.Scrollbar(self.page_view, orient="vertical", command=self.page_canvas.yview)
        self.page_scrollbar.grid(row=0, column=1, sticky="ns")
        self.page_canvas.configure(yscrollcommand=self.page_scrollbar.set)
        self.page_host = tk.Frame(self.page_canvas, bg=C["page"])
        self.page_window = self.page_canvas.create_window((0, 0), window=self.page_host, anchor="nw")
        self.page_host.bind("<Configure>", self._update_page_scrollregion)
        self.page_canvas.bind("<Configure>", self._resize_page_content)
        self.page_canvas.bind("<Enter>", self._bind_page_wheel)
        self.page_canvas.bind("<Leave>", self._unbind_page_wheel)
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)
        self._build_pages()
        self._build_statusbar()
        self._show_page("Overview")

    def _update_page_scrollregion(self, _event=None):
        self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))

    def _resize_page_content(self, event):
        self.page_canvas.itemconfigure(self.page_window, width=event.width)
        self._update_page_scrollregion()

    def _bind_page_wheel(self, _event=None):
        self.bind_all("<MouseWheel>", self._scroll_page_wheel)
        self.bind_all("<Button-4>", self._scroll_page_wheel)
        self.bind_all("<Button-5>", self._scroll_page_wheel)

    def _unbind_page_wheel(self, _event=None):
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _scroll_page_wheel(self, event):
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -int(event.delta / 120) if event.delta else 0
        if delta:
            self.page_canvas.yview_scroll(delta, "units")
        return "break"

    def _build_sidebar(self):
        self.brand = tk.Frame(self.sidebar, bg=C["nav"])
        self.brand.pack(fill="x", padx=18, pady=(21, 21))
        self.brand_icon = tk.Label(self.brand, text="B", bg=C["teal"], fg=C["white"], width=2,
                                   font=(FONT, 16, "bold"), padx=4, pady=2)
        self.brand_icon.pack(side="left")
        self.brand_text = tk.Frame(self.brand, bg=C["nav"])
        self.brand_text.pack(side="left", padx=10)
        tk.Label(self.brand_text, text="BASKET INSIGHTS", bg=C["nav"], fg=C["white"], font=(FONT, 11, "bold")).pack(anchor="w")
        tk.Label(self.brand_text, text="RETAIL ANALYTICS", bg=C["nav"], fg="#90a4c1", font=(FONT, 8, "bold")).pack(anchor="w", pady=(3, 0))
        self.nav_area = tk.Frame(self.sidebar, bg=C["nav"])
        self.nav_area.pack(fill="both", expand=True, padx=12)
        self._nav_label("WORKSPACE")
        self._nav_item("Overview", "⌂", "Overview")
        self._nav_group("Basket patterns", "⇄", (("Rules explorer", "Rules Explorer"), ("Frequent itemsets", "Frequent Itemsets")))
        self._nav_label("ANALYTICS")
        self._nav_group("Insights & reports", "◈", (("Algorithm lab", "Algorithm Lab"), ("Chart studio", "Chart Studio"), ("Reports & exports", "Reports & Exports")))
        self._nav_label("DATA")
        self._nav_item("Dataset settings", "⚙", "Dataset Settings")
        spacer = tk.Frame(self.nav_area, bg=C["nav"])
        spacer.pack(fill="both", expand=True)
        self.student_card = tk.Frame(self.sidebar, bg=C["nav2"], highlightbackground="#2b4264", highlightthickness=1)
        self.student_card.pack(fill="x", padx=14, pady=(5, 16))
        tk.Label(self.student_card, text="UN", bg="#2e4770", fg="white", width=3, height=1, font=(FONT, 10, "bold")).pack(side="left", padx=10, pady=11)
        self.student_text = tk.Frame(self.student_card, bg=C["nav2"])
        self.student_text.pack(side="left", pady=8)
        tk.Label(self.student_text, text="Muhammad Usman Nazir", bg=C["nav2"], fg="white", font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(self.student_text, text="24PWDSC0178", bg=C["nav2"], fg="#aebdd2", font=(FONT, 8)).pack(anchor="w", pady=(3, 0))

    def _nav_label(self, text):
        label = tk.Label(self.nav_area, text=text, bg=C["nav"], fg="#7f93b0", font=(FONT, 8, "bold"), anchor="w")
        label.pack(fill="x", padx=12, pady=(13, 7))
        self.nav_headers.append((label, text))

    def _nav_item(self, label, icon, page, parent=None):
        row = tk.Frame(parent or self.nav_area, bg=C["nav"])
        row.pack(fill="x", pady=2)
        indicator = tk.Frame(row, bg=C["nav"], width=3)
        indicator.pack(side="left", fill="y")
        btn = tk.Button(row, text=f"{icon}     {label}", anchor="w", bg=C["nav"], fg="#c2ccda",
                        activebackground=C["nav2"], activeforeground="white", relief="flat", bd=0,
                        font=(FONT, 9), padx=13, pady=10, command=lambda p=page: self._show_page(p))
        btn.pack(side="left", fill="x", expand=True)
        self.nav_buttons[page] = (row, indicator, btn, icon, label)

    def _nav_group(self, label, icon, children):
        group = tk.Frame(self.nav_area, bg=C["nav"])
        group.pack(fill="x", pady=2)
        button = tk.Button(group, text=f"{icon}     {label}     ⌄", anchor="w", bg=C["nav"], fg="#c2ccda",
                           activebackground=C["nav2"], activeforeground="white", relief="flat", bd=0,
                           font=(FONT, 9), padx=13, pady=10, command=lambda name=label: self._toggle_group(name))
        button.pack(fill="x")
        child_frame = tk.Frame(group, bg=C["nav"])
        for child_label, page in children:
            self._nav_item(child_label, "·", page, parent=child_frame)
        child_frame.pack(fill="x", padx=(13, 0))
        self.nav_groups[label] = {"frame": child_frame, "button": button, "open": True, "icon": icon, "pages": [p for _, p in children]}

    def _toggle_group(self, name):
        group = self.nav_groups[name]
        group["open"] = not group["open"]
        if group["open"]:
            group["frame"].pack(fill="x", padx=(13, 0))
        else:
            group["frame"].pack_forget()
        group["button"].configure(text=f"{group['icon']}     {name}     {'⌄' if group['open'] else '›'}")

    def _build_header(self):
        self.header = tk.Frame(self.workspace, bg=C["surface"], height=76, highlightbackground=C["line"], highlightthickness=1)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)
        self.header.grid_columnconfigure(2, weight=1)
        self.menu_btn = tk.Button(self.header, text="☰", bg=C["surface"], fg=C["ink"], bd=0, relief="flat",
                                  font=(FONT, 15), command=self._toggle_sidebar)
        self.menu_btn.grid(row=0, column=0, padx=(22, 18), pady=16)
        self.title_box = tk.Frame(self.header, bg=C["surface"])
        self.title_box.grid(row=0, column=1, sticky="w", pady=12)
        self.page_title = tk.Label(self.title_box, text="Overview", bg=C["surface"], fg=C["ink"], font=(FONT, 14, "bold"))
        self.page_title.pack(anchor="w")
        self.breadcrumb = tk.Label(self.title_box, text="Workspace  /  Overview", bg=C["surface"], fg=C["muted"], font=(FONT, 8))
        self.breadcrumb.pack(anchor="w", pady=(3, 0))

        search_wrap = tk.Frame(self.header, bg="#f7f9fc", highlightbackground=C["line"], highlightthickness=1)
        search_wrap.grid(row=0, column=2, sticky="ew", padx=(28, 18), pady=17)
        tk.Label(search_wrap, text="⌕", bg="#f7f9fc", fg=C["muted"], font=(FONT, 15)).pack(side="left", padx=(10, 4))
        self.search_entry = ttk.Entry(search_wrap, textvariable=self.global_search)
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=3, padx=(0, 8))
        self.search_entry.insert(0, "Search rules or products")
        self.search_entry.bind("<FocusIn>", self._clear_search_hint)
        self.search_entry.bind("<KeyRelease>", lambda _e: self._global_search_changed())
        tk.Button(search_wrap, text="Ctrl+F", bg="#eef2f7", fg=C["muted"], bd=0, font=(FONT, 8), padx=6, pady=3,
                  command=lambda: self.search_entry.focus_set()).pack(side="right", padx=7)

        self.range_button = ttk.Button(self.header, text="All data  ▾", command=self._show_range_info)
        self.range_button.grid(row=0, column=3, padx=(0, 12), pady=18)
        self.notify_button = tk.Button(self.header, text="♧", bg=C["surface"], fg=C["ink"], bd=0, font=(FONT, 14),
                                       command=self._notifications)
        self.notify_button.grid(row=0, column=4, padx=7)
        self.profile_button = tk.Button(self.header, text="UN  ▾", bg="#e9eff9", fg=C["ink"], bd=0,
                                        font=(FONT, 9, "bold"), padx=10, pady=8, command=self._profile)
        self.profile_button.grid(row=0, column=5, padx=(7, 22))

    def _build_statusbar(self):
        bar = tk.Frame(self.workspace, bg=C["surface"], height=33, highlightbackground=C["line"], highlightthickness=1)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_propagate(False)
        tk.Label(bar, textvariable=self.status, bg=C["surface"], fg=C["muted"], font=(FONT, 8)).pack(side="left", padx=22, pady=7)
        self.status_right = tk.Label(bar, text="LOCAL ANALYSIS  •  DS-A38", bg=C["surface"], fg="#8795a8", font=(FONT, 8, "bold"))
        self.status_right.pack(side="right", padx=22)

    # -------------------------------------------------------------- navigation
    def _toggle_sidebar(self):
        target = 74 if self.sidebar_open else 252
        step = -22 if self.sidebar_open else 22
        self.sidebar_open = not self.sidebar_open
        self._sidebar_animation(self.sidebar_width, target, step)

    def _sidebar_animation(self, width, target, step):
        nxt = width + step
        if (step < 0 and nxt < target) or (step > 0 and nxt > target):
            nxt = target
        self.sidebar_width = nxt
        self.sidebar.configure(width=nxt)
        self.grid_columnconfigure(0, minsize=nxt)
        collapsed = nxt <= 100
        self.brand_text.pack_forget() if collapsed else self.brand_text.pack(side="left", padx=10)
        for header, text in self.nav_headers:
            header.configure(text="" if collapsed else text)
            header.pack_configure(pady=(4, 4) if collapsed else (13, 7))
        for name, group in self.nav_groups.items():
            if collapsed:
                group["frame"].pack_forget()
            elif group["open"] and not group["frame"].winfo_manager():
                group["frame"].pack(fill="x", padx=(13, 0))
            group["button"].configure(text=group["icon"] if collapsed else f"{group['icon']}     {name}     {'⌄' if group['open'] else '›'}")
        for page, (row, indicator, button, icon, label) in self.nav_buttons.items():
            button.configure(text=icon if collapsed else f"{icon}     {label}", anchor="center" if collapsed else "w")
        if collapsed:
            self.student_text.pack_forget()
        elif not self.student_text.winfo_manager():
            self.student_text.pack(side="left", pady=8)
        if (step < 0 and nxt > target) or (step > 0 and nxt < target):
            self.after(12, lambda: self._sidebar_animation(nxt, target, step))

    def _show_page(self, page):
        if page not in self.page_frames:
            return
        self.active_page = page
        for frame in self.page_frames.values():
            frame.grid_remove()
        self.page_frames[page].grid(row=0, column=0, sticky="nsew")
        self.page_title.configure(text=page)
        section = "Workspace" if page in ("Overview", "Rules Explorer", "Frequent Itemsets") else "Analytics" if page in ("Algorithm Lab", "Chart Studio", "Reports & Exports") else "Data"
        self.breadcrumb.configure(text=f"{section}  /  {page}")
        for p, (_, indicator, btn, _, _) in self.nav_buttons.items():
            active = p == page
            indicator.configure(bg=C["teal"] if active else C["nav"])
            btn.configure(bg=C["nav2"] if active else C["nav"], fg=C["white"] if active else "#c2ccda")
        for group in self.nav_groups.values():
            active = page in group["pages"]
            group["button"].configure(bg=C["nav2"] if active else C["nav"], fg=C["white"] if active else "#c2ccda")
        if page == "Chart Studio":
            self._draw_studio_chart()
        if page == "Rules Explorer":
            self._refresh_rules()
        if page == "Frequent Itemsets":
            self._refresh_itemsets()

    # --------------------------------------------------------------- page build
    def _build_pages(self):
        makers = {
            "Overview": self._page_overview,
            "Rules Explorer": self._page_rules,
            "Frequent Itemsets": self._page_itemsets,
            "Algorithm Lab": self._page_algorithms,
            "Chart Studio": self._page_charts,
            "Reports & Exports": self._page_reports,
            "Dataset Settings": self._page_settings,
        }
        for name, maker in makers.items():
            frame = tk.Frame(self.page_host, bg=C["page"])
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_columnconfigure(0, weight=1)
            self.page_frames[name] = frame
            maker(frame)

    def _page_overview(self, frame):
        frame.grid_rowconfigure(2, weight=1)
        head = tk.Frame(frame, bg=C["page"])
        head.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        head.grid_columnconfigure(0, weight=1)
        tk.Label(head, text="Good to see you, Usman", bg=C["page"], fg=C["ink"], font=(FONT, 21, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(head, text="A focused view of your grocery basket patterns and algorithm results.", bg=C["page"], fg=C["muted"], font=(FONT, 10)).grid(row=1, column=0, sticky="w", pady=(4, 0))
        actions = tk.Frame(head, bg=C["page"])
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        self._button(actions, "＋  Import dataset", self._browse, style="light").pack(side="left", padx=5)
        self._button(actions, "Export report", self._export_menu, style="light").pack(side="left", padx=5)
        self.overview_run_button = self._button(actions, "▶  Run analysis", self._run_analysis, style="primary")
        self.overview_run_button.pack(side="left", padx=5)
        self.run_buttons.append((self.overview_run_button, "▶  Run analysis"))

        controls = self._card(frame)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        controls.grid_columnconfigure(1, weight=1)
        tk.Label(controls, text="DATA SOURCE", bg=C["surface"], fg=C["muted"], font=(FONT, 8, "bold")).grid(row=0, column=0, padx=(15, 8), pady=13)
        ttk.Entry(controls, textvariable=self.data_path).grid(row=0, column=1, sticky="ew", padx=4, pady=10)
        self._button(controls, "Browse", self._browse, style="light").grid(row=0, column=2, padx=10, pady=9)
        self._threshold_entry(controls, "Support", self.min_support, 3)
        self._threshold_entry(controls, "Confidence", self.min_confidence, 4)
        self._threshold_entry(controls, "Lift", self.min_lift, 5)

        body = tk.Frame(frame, bg=C["page"])
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure((0, 1, 2), weight=1, uniform="kpi")
        body.grid_rowconfigure(3, weight=1)
        specs = [
            ("Baskets analyzed", "transactions", "Input coverage", C["blue"], "▣"),
            ("Distinct products", "distinct_items", "Catalog breadth", C["teal"], "◈"),
            ("Average basket", "avg_basket", "Products per basket", C["purple"], "▤"),
            ("Frequent itemsets", "itemsets", "At selected support", C["orange"], "▦"),
            ("Distinct rules", "rules", "After deduplication", C["blue"], "⇄"),
            ("Best lift", "best_lift", "Compared with independence", C["green"], "↗"),
        ]
        self.kpis = {}
        for i, (title, key, note, accent, icon) in enumerate(specs):
            card = self._kpi_card(body, title, key, note, accent, icon)
            card.grid(row=i // 3, column=i % 3, sticky="ew", padx=(0 if i % 3 == 0 else 7, 7 if i % 3 < 2 else 0), pady=(0, 12))
        charts = tk.Frame(body, bg=C["page"])
        charts.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(3, 13))
        charts.grid_columnconfigure((0, 1, 2), weight=1, uniform="charts")
        self.overview_chart_frames = []
        for index in range(6):
            row, col = divmod(index, 3)
            chart_card = self._card(charts)
            chart_card.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 7, 7 if col < 2 else 0), pady=(0, 10))
            self.overview_chart_frames.append(chart_card)
        self.insight_card = self._card(body)
        self.insight_card.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 5))
        self._label(self.insight_card, "INSIGHT SPOTLIGHT", size=8, color=C["teal"], bold=True).pack(anchor="w", padx=16, pady=(13, 4))
        self.insight_text = tk.Label(self.insight_card, text="Run an analysis to surface a concise, evidence-based finding.", bg=C["surface"], fg=C["ink"], font=(FONT, 10), wraplength=1000, justify="left")
        self.insight_text.pack(anchor="w", padx=16, pady=(0, 14))

    def _page_rules(self, frame):
        frame.grid_rowconfigure(2, weight=1)
        self._page_heading(frame, "Association rules", "Search, filter, sort, and export the strongest product relationships.", 0)
        toolbar = self._card(frame)
        toolbar.grid(row=1, column=0, sticky="new", pady=(0, 11))
        toolbar.grid_columnconfigure(1, weight=1)
        self.rule_search_entry = ttk.Entry(toolbar, textvariable=self.rule_search)
        self.rule_search_entry.grid(row=0, column=0, sticky="ew", padx=(13, 8), pady=12)
        self.rule_search_entry.configure(width=28)
        self.rule_search_entry.insert(0, "Filter by product…")
        self.rule_search_entry.bind("<FocusIn>", self._clear_rule_hint)
        self.rule_search_entry.bind("<KeyRelease>", lambda _e: self._refresh_rules(reset=True))
        tk.Label(toolbar, text="Method", bg=C["surface"], fg=C["muted"], font=(FONT, 9)).grid(row=0, column=2, padx=(6, 4))
        ttk.Combobox(toolbar, textvariable=self.rule_algorithm, values=("All methods", "Apriori", "FP-Growth", "Both"), width=13, state="readonly").grid(row=0, column=3, padx=5)
        tk.Label(toolbar, text="Min lift", bg=C["surface"], fg=C["muted"], font=(FONT, 9)).grid(row=0, column=4, padx=(7, 3))
        lift_entry = ttk.Entry(toolbar, textvariable=self.rule_min_lift, width=8)
        lift_entry.grid(row=0, column=5, padx=(2, 7))
        lift_entry.bind("<KeyRelease>", lambda _e: self._refresh_rules(reset=True))
        self.rule_algorithm.trace_add("write", lambda *_: self._refresh_rules(reset=True))
        self._button(toolbar, "Columns ▾", self._column_menu, style="light").grid(row=0, column=6, padx=4, pady=8)
        self._button(toolbar, "Export ▾", self._export_menu, style="light").grid(row=0, column=7, padx=(4, 12), pady=8)

        table_card = self._card(frame)
        table_card.grid(row=2, column=0, sticky="nsew")
        table_card.grid_rowconfigure(1, weight=1)
        table_card.grid_columnconfigure(0, weight=1)
        self.rule_count_label = tk.Label(table_card, text="No results loaded", bg=C["surface"], fg=C["muted"], font=(FONT, 9))
        self.rule_count_label.grid(row=0, column=0, sticky="w", padx=15, pady=11)
        self.rule_tree = self._tree(table_card, ("algorithm", "antecedents", "consequents", "support", "confidence", "lift"),
                                    ("Method", "Basket contains", "Also likely", "Support", "Confidence", "Lift"),
                                    (100, 230, 230, 100, 110, 85), sort_callback=self._sort_rules)
        self.rule_tree.grid(row=1, column=0, sticky="nsew", padx=12)
        self.rule_tree_scroll = ttk.Scrollbar(table_card, orient="vertical", command=self.rule_tree.yview)
        self.rule_tree.configure(yscrollcommand=self.rule_tree_scroll.set)
        self.rule_tree_scroll.grid(row=1, column=1, sticky="ns", pady=1, padx=(0, 12))
        footer = tk.Frame(table_card, bg=C["surface"])
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=10)
        self.page_label = tk.Label(footer, text="Page 1", bg=C["surface"], fg=C["muted"], font=(FONT, 9))
        self.page_label.pack(side="left")
        self._button(footer, "‹ Previous", lambda: self._change_rule_page(-1), style="light").pack(side="right", padx=3)
        self._button(footer, "Next ›", lambda: self._change_rule_page(1), style="light").pack(side="right", padx=3)

    def _page_itemsets(self, frame):
        frame.grid_rowconfigure(2, weight=1)
        self._page_heading(frame, "Frequent itemsets", "Products that occur together often enough to pass the selected support threshold.", 0)
        toolbar = self._card(frame)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.item_search = ttk.Entry(toolbar, width=42)
        self.item_search.insert(0, "Search itemsets…")
        self.item_search.pack(side="left", padx=13, pady=11)
        self.item_search.bind("<FocusIn>", lambda e: self._placeholder_clear(e, "Search itemsets…"))
        self.item_search.bind("<KeyRelease>", lambda _e: self._refresh_itemsets())
        self._button(toolbar, "Export ▾", self._export_menu, style="light").pack(side="right", padx=12, pady=8)
        table = self._card(frame)
        table.grid(row=2, column=0, sticky="nsew")
        table.grid_rowconfigure(0, weight=1); table.grid_columnconfigure(0, weight=1)
        self.item_tree = self._tree(table, ("itemsets", "support", "basket_count", "size"),
                                    ("Itemset", "Support", "Baskets", "Items"), (440, 120, 120, 100), sort_callback=self._sort_itemsets)
        self.item_tree.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=12)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=scroll.set); scroll.grid(row=0, column=1, sticky="ns", pady=12, padx=(0, 12))

    def _page_algorithms(self, frame):
        frame.grid_rowconfigure(3, weight=1)
        self._page_heading(frame, "Algorithm lab", "Compare candidate-generation and pattern-growth approaches on the same baskets.", 0)
        top = tk.Frame(frame, bg=C["page"])
        top.grid(row=1, column=0, sticky="new", pady=(0, 13))
        top.configure(height=122)
        top.grid_propagate(False)
        top.grid_rowconfigure(0, weight=1)
        top.grid_columnconfigure((0, 1), weight=1, uniform="algo")
        self.algo_cards = {}
        for col, name, accent in ((0, "Apriori", C["blue"]), (1, "FP-Growth", C["purple"])):
            card = self._card(top)
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 8 if col == 0 else 0))
            tk.Label(card, text=name, bg=C["surface"], fg=accent, font=(FONT, 15, "bold")).pack(anchor="w", padx=18, pady=(16, 4))
            detail = tk.Label(card, text="Run both methods to compare results.", bg=C["surface"], fg=C["muted"], font=(FONT, 10), justify="left")
            detail.pack(anchor="w", padx=18, pady=(0, 16))
            self.algo_cards[name] = detail
        lower = self._card(frame)
        lower.grid(row=2, column=0, sticky="ew", pady=(0, 13))
        tk.Label(lower, text="Runtime comparison", bg=C["surface"], fg=C["ink"], font=(FONT, 12, "bold")).pack(anchor="w", padx=15, pady=(13, 5))
        self.algorithm_chart_host = tk.Frame(lower, bg=C["surface"], height=250)
        self.algorithm_chart_host.pack(fill="x", padx=12, pady=(0, 12))
        self.algorithm_chart_host.pack_propagate(False)
        compare = self._card(frame)
        compare.grid(row=3, column=0, sticky="ew")
        tk.Label(compare, text="Results table", bg=C["surface"], fg=C["ink"], font=(FONT, 11, "bold")).pack(anchor="w", padx=15, pady=(13, 7))
        self.algorithm_tree = self._tree(compare, ("algorithm", "frequent_itemsets", "rules", "runtime_seconds"),
                                         ("Algorithm", "Frequent itemsets", "Rules", "Runtime (seconds)"), (220, 220, 160, 190))
        self.algorithm_tree.pack(fill="x", padx=12, pady=(0, 13))

    def _page_charts(self, frame):
        frame.grid_rowconfigure(2, weight=1)
        self._page_heading(frame, "Chart studio", "Explore product mix, basket size, rule strength, and algorithm runtime.", 0)
        controls = self._card(frame)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        tk.Label(controls, text="VISUALIZATION", bg=C["surface"], fg=C["muted"], font=(FONT, 8, "bold")).pack(side="left", padx=(14, 7))
        ttk.Combobox(controls, textvariable=self.chart_metric, state="readonly", width=27,
                     values=("Product frequency", "Basket size distribution", "Rule quality", "Algorithm runtime")).pack(side="left", padx=5, pady=10)
        tk.Label(controls, text="CHART TYPE", bg=C["surface"], fg=C["muted"], font=(FONT, 8, "bold")).pack(side="left", padx=(17, 7))
        ttk.Combobox(controls, textvariable=self.chart_kind, state="readonly", width=14,
                     values=("Bar", "Line", "Area", "Pie", "Doughnut")).pack(side="left", padx=5, pady=10)
        self._button(controls, "Refresh chart", self._draw_studio_chart, style="primary").pack(side="right", padx=13, pady=8)
        self.chart_metric.trace_add("write", lambda *_: self._draw_studio_chart())
        self.chart_kind.trace_add("write", lambda *_: self._draw_studio_chart())
        chart = self._card(frame)
        chart.grid(row=2, column=0, sticky="nsew")
        self.studio_chart_host = tk.Frame(chart, bg=C["surface"])
        self.studio_chart_host.pack(fill="both", expand=True, padx=9, pady=9)

    def _page_reports(self, frame):
        frame.grid_rowconfigure(2, weight=1)
        self._page_heading(frame, "Reports & exports", "Create portable analysis files for your report, review, and presentation.", 0)
        block = self._card(frame)
        block.grid(row=1, column=0, sticky="new", pady=(3, 14))
        tk.Label(block, text="Export analysis", bg=C["surface"], fg=C["ink"], font=(FONT, 14, "bold")).pack(anchor="w", padx=18, pady=(18, 5))
        tk.Label(block, text="Exports use the currently loaded analysis. Excel includes rules, itemsets, algorithm comparison, and summary sheets.", bg=C["surface"], fg=C["muted"], font=(FONT, 9), wraplength=860, justify="left").pack(anchor="w", padx=18, pady=(0, 14))
        actions = tk.Frame(block, bg=C["surface"]); actions.pack(anchor="w", padx=14, pady=(0, 18))
        self._button(actions, "Export Excel workbook  .xlsx", lambda: self._export("xlsx"), style="primary").pack(side="left", padx=4)
        self._button(actions, "Export rules  .csv", lambda: self._export("csv"), style="light").pack(side="left", padx=4)
        self._button(actions, "Export report  .pdf", lambda: self._export("pdf"), style="light").pack(side="left", padx=4)
        summary = self._card(frame)
        summary.grid(row=2, column=0, sticky="ew")
        tk.Label(summary, text="Report contents", bg=C["surface"], fg=C["ink"], font=(FONT, 12, "bold")).pack(anchor="w", padx=18, pady=(15, 8))
        self.report_summary = tk.Label(summary, text="Run the analysis to prepare a report summary.", bg=C["surface"], fg=C["muted"], font=(FONT, 9), justify="left", wraplength=960)
        self.report_summary.pack(anchor="w", padx=18, pady=(0, 16))

    def _page_settings(self, frame):
        frame.grid_rowconfigure(2, weight=1)
        self._page_heading(frame, "Dataset settings", "Manage the input file and association-rule thresholds.", 0)
        settings = self._card(frame)
        settings.grid(row=1, column=0, sticky="new", pady=(3, 13))
        tk.Label(settings, text="Source file", bg=C["surface"], fg=C["ink"], font=(FONT, 11, "bold")).grid(row=0, column=0, sticky="w", padx=17, pady=(17, 4))
        ttk.Entry(settings, textvariable=self.data_path, width=75).grid(row=1, column=0, sticky="ew", padx=17, pady=5)
        self._button(settings, "Browse for CSV", self._browse, style="light").grid(row=1, column=1, padx=12)
        tk.Label(settings, text="Minimum support", bg=C["surface"], fg=C["muted"], font=(FONT, 9)).grid(row=2, column=0, sticky="w", padx=17, pady=(15, 4))
        self._threshold_entry(settings, "", self.min_support, 2, row=3, compact=True)
        tk.Label(settings, text="Minimum confidence", bg=C["surface"], fg=C["muted"], font=(FONT, 9)).grid(row=2, column=1, sticky="w", padx=17, pady=(15, 4))
        self._threshold_entry(settings, "", self.min_confidence, 2, row=3, compact=True)
        tk.Label(settings, text="Minimum lift", bg=C["surface"], fg=C["muted"], font=(FONT, 9)).grid(row=2, column=2, sticky="w", padx=17, pady=(15, 4))
        self._threshold_entry(settings, "", self.min_lift, 2, row=3, compact=True)
        settings_run = self._button(settings, "Save settings & run", self._run_analysis, style="primary")
        settings_run.grid(row=4, column=0, sticky="w", padx=17, pady=17)
        self.run_buttons.append((settings_run, "Save settings & run"))
        note = self._card(frame); note.grid(row=2, column=0, sticky="ew")
        tk.Label(note, text="Date range", bg=C["surface"], fg=C["ink"], font=(FONT, 11, "bold")).pack(anchor="w", padx=17, pady=(15, 4))
        tk.Label(note, text="The selected transaction file has no date column in the basket format, so this dashboard analyzes all available baskets. It will not imply a time trend without dates.", bg=C["surface"], fg=C["muted"], font=(FONT, 9), wraplength=900, justify="left").pack(anchor="w", padx=17, pady=(0, 15))

    # --------------------------------------------------------- reusable widgets
    def _card(self, parent):
        return tk.Frame(parent, bg=C["surface"], highlightbackground=C["line"], highlightthickness=1)

    def _button(self, parent, text, command, style="light"):
        bg = C["teal"] if style == "primary" else C["surface"]
        fg = C["white"] if style == "primary" else C["ink"]
        hover = "#0f746c" if style == "primary" else "#f0f4f8"
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=hover,
                         activeforeground=fg, relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=C["line"] if style != "primary" else C["teal"],
                         font=(FONT, 9, "bold"), padx=12, pady=8, cursor="hand2")

    def _label(self, parent, text, size=10, color=None, bold=False):
        return tk.Label(parent, text=text, bg=C["surface"], fg=color or C["ink"], font=(FONT, size, "bold" if bold else "normal"))

    def _page_heading(self, parent, title, subtitle, row):
        box = tk.Frame(parent, bg=C["page"])
        box.grid(row=row, column=0, sticky="ew", pady=(0, 15))
        tk.Label(box, text=title, bg=C["page"], fg=C["ink"], font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(box, text=subtitle, bg=C["page"], fg=C["muted"], font=(FONT, 9)).pack(anchor="w", pady=(4, 0))

    def _threshold_entry(self, parent, label, var, col, row=0, compact=False):
        box = tk.Frame(parent, bg=C["surface"])
        box.grid(row=row, column=col, padx=(8, 10), pady=5, sticky="w")
        if label:
            tk.Label(box, text=label, bg=C["surface"], fg=C["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 3))
        ttk.Entry(box, textvariable=var, width=9 if compact else 8).pack(anchor="w")

    def _kpi_card(self, parent, title, key, note, accent, icon):
        card = self._card(parent)
        card.grid_columnconfigure(0, weight=1)
        head = tk.Frame(card, bg=C["surface"]); head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        tk.Label(head, text=title, bg=C["surface"], fg=C["muted"], font=(FONT, 9, "bold")).pack(side="left")
        tk.Label(head, text=icon, bg=C["surface"], fg=accent, font=(FONT, 14, "bold")).pack(side="right")
        value = tk.Label(card, text="—", bg=C["surface"], fg=C["ink"], font=(FONT, 24, "bold"))
        value.grid(row=1, column=0, sticky="w", padx=14, pady=(2, 0))
        foot = tk.Frame(card, bg=C["surface"]); foot.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
        dot = tk.Label(foot, text="●", bg=C["surface"], fg=accent, font=(FONT, 7)); dot.pack(side="left", padx=(0, 5))
        info = tk.Label(foot, text=note, bg=C["surface"], fg=C["muted"], font=(FONT, 8)); info.pack(side="left")
        self.kpis[key] = (value, info, accent)
        return card

    def _tree(self, parent, cols, labels, widths, sort_callback=None):
        tree = ttk.Treeview(parent, columns=cols, show="headings")
        for col, label, width in zip(cols, labels, widths):
            options = {"text": label}
            if sort_callback:
                options["command"] = lambda c=col: sort_callback(c)
            tree.heading(col, **options)
            tree.column(col, width=width, anchor="w" if col in ("antecedents", "consequents", "itemsets") else "center", stretch=True)
        tree.tag_configure("even", background="#f7f9fc")
        tree.tag_configure("odd", background=C["surface"])
        return tree

    # --------------------------------------------------------------- data runs
    def _browse(self):
        path = filedialog.askopenfilename(title="Select basket transactions", initialdir=ROOT / "data",
                                          filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))
        if path:
            self.data_path.set(path)

    def _run_analysis(self):
        try:
            support, confidence, lift = float(self.min_support.get()), float(self.min_confidence.get()), float(self.min_lift.get())
            if not (0 < support <= 1 and 0 <= confidence <= 1 and lift >= 0):
                raise ValueError("Support and confidence must be between 0 and 1; lift must be zero or greater.")
            if not Path(self.data_path.get()).is_file():
                raise ValueError("Choose an existing CSV dataset.")
        except ValueError as exc:
            messagebox.showerror("Review analysis settings", str(exc), parent=self)
            return
        self.status.set("Preparing transactions…")
        self._set_busy(True)
        threading.Thread(target=self._worker, args=(support, confidence, lift), daemon=True).start()

    def _set_busy(self, busy):
        for button, label in self.run_buttons:
            button.configure(state="disabled" if busy else "normal", text="Analysis running…" if busy else label)

    def _worker(self, support, confidence, lift):
        try:
            result = run_pipeline(self.data_path.get(), support, confidence, lift, OUT,
                                  progress=lambda msg: self.events.put(("status", msg)))
            transactions = load_transactions(self.data_path.get())
            encoded = encode_transactions(transactions)
            self.events.put(("success", (result, transactions, encoded)))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status.set(payload)
                elif kind == "success":
                    self._apply_result(*payload)
                    self._set_busy(False)
                elif kind == "error":
                    self.status.set("Analysis did not complete")
                    self._set_busy(False)
                    messagebox.showerror("Analysis error", payload, parent=self)
        except queue.Empty:
            pass
        self.after(120, self._poll_events)

    def _apply_result(self, result, transactions, encoded):
        self.transactions = transactions
        self.summary = result["summary"]
        self.comparison = result["comparison"]
        self.rule_data = result["rules"].copy()
        self.frequency_data = encoded.sum().sort_values(ascending=False)
        self._read_itemsets()
        self._update_kpis()
        self._refresh_rules(reset=True)
        self._refresh_itemsets()
        self._update_algorithm_page()
        self._draw_overview_charts()
        self._draw_studio_chart()
        self._update_report_summary()
        self.status.set(f"Analysis complete · {len(transactions):,} baskets · files saved in {OUT}")

    def _read_itemsets(self):
        path = OUT / "apriori_frequent_itemsets.csv"
        self.itemset_data = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["support", "itemsets"])
        if not self.itemset_data.empty:
            self.itemset_data["size"] = self.itemset_data["itemsets"].map(lambda s: len([x for x in str(s).split(",") if x.strip()]))
            self.itemset_data["basket_count"] = (self.itemset_data["support"] * len(self.transactions)).round().astype(int)

    def _load_existing(self):
        summary_path, compare_path, rules_path = OUT / "dataset_summary.json", OUT / "algorithm_comparison.csv", OUT / "ranked_rules.csv"
        try:
            if summary_path.exists() and compare_path.exists() and rules_path.exists():
                self.summary = json.loads(summary_path.read_text(encoding="utf-8"))
                self.comparison = pd.read_csv(compare_path).to_dict("records")
                self.rule_data = pd.read_csv(rules_path)
                self.transactions = load_transactions(self.data_path.get())
                encoded = encode_transactions(self.transactions)
                self.frequency_data = encoded.sum().sort_values(ascending=False)
                self._read_itemsets()
                self._update_kpis()
                self._refresh_rules(reset=True)
                self._refresh_itemsets()
                self._update_algorithm_page()
                self._draw_overview_charts()
                self._update_report_summary()
                self.status.set("Showing the latest saved analysis")
        except Exception as exc:
            self.status.set(f"Saved results could not be loaded: {exc}")

    # -------------------------------------------------------------- KPI/chart
    def _update_kpis(self):
        if not self.summary:
            return
        rules = self.rule_data.drop_duplicates(["antecedents", "consequents"]) if not self.rule_data.empty else self.rule_data
        best = float(rules["lift"].max()) if not rules.empty else 0.0
        avg = float(self.summary.get("average_basket_size", 0))
        vals = {
            "transactions": (f"{self.summary.get('transactions', 0):,}", "All available baskets"),
            "distinct_items": (f"{self.summary.get('distinct_items', 0):,}", "Distinct products observed"),
            "avg_basket": (f"{avg:.2f}", "Average distinct items / basket"),
            "itemsets": (f"{len(self.itemset_data):,}", f"Support ≥ {self.min_support.get()}"),
            "rules": (f"{len(rules):,}", "Unique rules · both algorithms"),
            "best_lift": (f"{best:.2f}×", f"{(best-1)*100:+.1f}% vs independence" if best else "No rules at these thresholds"),
        }
        for key, (value, note) in vals.items():
            self.kpis[key][0].configure(text=value)
            self.kpis[key][1].configure(text=note)
        self._set_kpi_comparison()
        if not rules.empty:
            top = rules.sort_values(["lift", "support"], ascending=False).iloc[0]
            self.insight_text.configure(text=f"Top pattern: {top['antecedents']} → {top['consequents']}  |  support {top['support']:.1%}  |  confidence {top['confidence']:.1%}  |  lift {top['lift']:.2f}×. Lift compares confidence against the consequent’s baseline popularity; high confidence alone can overstate a bundle opportunity.")

    def _set_kpi_comparison(self):
        if len(self.comparison) < 2:
            return
        a, b = self.comparison[0], self.comparison[1]
        match = a["frequent_itemsets"] == b["frequent_itemsets"] and a["rules"] == b["rules"]
        self.kpis["itemsets"][1].configure(text=f"Apriori / FP-Growth {'✓ match' if match else 'review outputs'}")

    def _draw_overview_charts(self):
        chart_specs = [
            ("Most purchased products", self._chart_products),
            ("Basket size distribution", self._chart_baskets),
            ("Top rules by lift", self._chart_rule_lift),
            ("Rule support vs confidence", self._chart_rule_scatter),
            ("Algorithm runtime", self._chart_runtime),
            ("Frequent itemsets by size", self._chart_itemset_sizes),
        ]
        for host, (title, draw) in zip(self.overview_chart_frames, chart_specs):
            self._embed_chart(host, title, draw, figsize=(4.5, 2.45))

    def _chart_rule_lift(self, ax):
        if self.rule_data.empty:
            ax.text(.5, .5, "Run analysis to see association rules", ha="center", va="center", color=C["muted"], transform=ax.transAxes); return
        rules = self.rule_data.drop_duplicates(["antecedents", "consequents"]).nlargest(8, "lift").sort_values("lift")
        labels = [f"{str(a)[:16]} → {str(b)[:16]}" for a, b in zip(rules.antecedents, rules.consequents)]
        ax.barh(labels, rules.lift, color=C["purple"]); ax.set_xlabel("Lift (×)", color=C["muted"], fontsize=8)
        ax.grid(axis="x", color=C["line"], linewidth=.8); ax.set_axisbelow(True); ax.spines[["top", "right", "left"]].set_visible(False); ax.tick_params(colors=C["muted"], labelsize=7)

    def _chart_rule_scatter(self, ax):
        if self.rule_data.empty:
            ax.text(.5, .5, "Run analysis to compare rule quality", ha="center", va="center", color=C["muted"], transform=ax.transAxes); return
        rules = self.rule_data.drop_duplicates(["antecedents", "consequents"])
        points = ax.scatter(rules.support, rules.confidence, c=rules.lift, cmap="viridis", s=30, alpha=.75, edgecolors="white", linewidths=.4)
        ax.set_xlabel("Support", fontsize=8, color=C["muted"]); ax.set_ylabel("Confidence", fontsize=8, color=C["muted"])
        ax.grid(color=C["line"], linewidth=.7); ax.set_axisbelow(True); ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(colors=C["muted"], labelsize=7); ax.figure.colorbar(points, ax=ax, fraction=.05, pad=.04, label="Lift")

    def _chart_runtime(self, ax):
        if not self.comparison:
            ax.text(.5, .5, "Run both algorithms to compare runtime", ha="center", va="center", color=C["muted"], transform=ax.transAxes); return
        labels = ["Apriori" if x["algorithm"] == "apriori" else "FP-Growth" for x in self.comparison]
        values = [x["runtime_seconds"] for x in self.comparison]
        bars = ax.bar(labels, values, color=[C["blue"], C["teal"]][:len(values)], width=.55)
        ax.set_ylabel("Seconds", fontsize=8, color=C["muted"]); ax.grid(axis="y", color=C["line"], linewidth=.7); ax.set_axisbelow(True)
        ax.spines[["top", "right", "left"]].set_visible(False); ax.tick_params(colors=C["muted"], labelsize=8)
        for bar, value in zip(bars, values): ax.annotate(f"{value:.3f}s", (bar.get_x()+bar.get_width()/2, bar.get_height()), ha="center", xytext=(0, 3), textcoords="offset points", fontsize=8, color=C["muted"])

    def _chart_itemset_sizes(self, ax):
        if self.itemset_data.empty or "size" not in self.itemset_data:
            ax.text(.5, .5, "No frequent itemsets at these thresholds", ha="center", va="center", color=C["muted"], transform=ax.transAxes); return
        counts = self.itemset_data.groupby("size").size()
        ax.bar(counts.index.astype(str), counts.values, color=C["orange"], width=.6)
        ax.set_xlabel("Products per itemset", fontsize=8, color=C["muted"]); ax.set_ylabel("Itemsets", fontsize=8, color=C["muted"])
        ax.grid(axis="y", color=C["line"], linewidth=.7); ax.set_axisbelow(True); ax.spines[["top", "right", "left"]].set_visible(False); ax.tick_params(colors=C["muted"], labelsize=8)

    def _draw_studio_chart(self):
        if not hasattr(self, "studio_chart_host"):
            return
        metric = self.chart_metric.get()
        kind = self.chart_kind.get().lower()
        def draw(ax):
            if metric == "Product frequency":
                labels, vals = list(self.frequency_data.head(10).index), list(self.frequency_data.head(10).values)
                self._plot_series(ax, labels, vals, kind, ylabel="Baskets containing product", title="Most frequent products")
            elif metric == "Basket size distribution":
                counts = pd.Series([len(set(t)) for t in self.transactions]).value_counts().sort_index()
                self._plot_series(ax, [str(x) for x in counts.index], list(counts.values), kind, ylabel="Number of baskets", title="Basket size distribution", pie_label="items")
            elif metric == "Rule quality":
                rules = self.rule_data.drop_duplicates(["antecedents", "consequents"]) if not self.rule_data.empty else self.rule_data
                rules = rules.sort_values(["lift", "support"], ascending=False).head(10)
                labels = [f"{x} → {y}" for x,y in zip(rules.get("antecedents", []), rules.get("consequents", []))]
                vals = list(rules.get("lift", []))
                self._plot_series(ax, labels, vals, kind, ylabel="Lift", title="Lift of top rules")
            else:
                comp = self.comparison
                labels = ["Apriori" if x["algorithm"] == "apriori" else "FP-Growth" for x in comp]
                vals = [x["runtime_seconds"] for x in comp]
                self._plot_series(ax, labels, vals, kind, ylabel="Seconds", title="Algorithm runtime")
        self._embed_chart(self.studio_chart_host, f"{metric} · {kind}", draw, figsize=(10.5, 6.0), replace=True)

    def _chart_products(self, ax, kind="bar"):
        counts = self.frequency_data.head(10).sort_values()
        ax.barh(counts.index, counts.values, color=C["teal"], height=.68)
        ax.set_xlabel("Baskets containing product", color=C["muted"])
        ax.grid(axis="x", color=C["line"], linewidth=.8); ax.set_axisbelow(True)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(colors=C["muted"], labelsize=8)

    def _chart_baskets(self, ax, kind="donut"):
        sizes = pd.Series([len(set(t)) for t in self.transactions]).value_counts().sort_index()
        if sizes.empty:
            return
        labels = [f"{x} items" for x in sizes.index]
        wedges, _, _ = ax.pie(sizes.values, labels=None, autopct="%1.0f%%", startangle=90,
                              colors=[C["teal"], C["blue"], C["orange"], C["purple"], C["green"]][:len(sizes)],
                              wedgeprops={"width": .42} if kind == "donut" else {})
        ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(.86, .5), frameon=False, fontsize=8)
        ax.set_aspect("equal")

    def _plot_series(self, ax, labels, values, kind, ylabel, title, pie_label=""):
        if len(values) == 0:
            ax.text(.5, .5, "Run the analysis to load chart data", ha="center", va="center", color=C["muted"], transform=ax.transAxes)
            return
        colors = [C["teal"], C["blue"], C["orange"], C["purple"], C["green"]]
        x = list(range(len(values)))
        if kind in ("pie", "doughnut"):
            short = [str(x)[:24] for x in labels]
            wedges, _, _ = ax.pie(values, startangle=90, autopct="%1.0f%%", labels=None,
                                  colors=(colors * (len(values)//len(colors)+1))[:len(values)],
                                  wedgeprops={"width": .42} if kind == "doughnut" else {})
            ax.legend(wedges, short, loc="center left", bbox_to_anchor=(.86, .5), frameon=False, fontsize=8)
            ax.set_aspect("equal")
        elif kind == "line":
            ax.plot(x, values, color=C["blue"], marker="o", linewidth=2.4, markersize=6)
            ax.fill_between(x, values, color=C["blue"], alpha=.08)
        elif kind == "area":
            ax.fill_between(x, values, color=C["teal"], alpha=.24)
            ax.plot(x, values, color=C["teal"], linewidth=2)
        else:
            bars = ax.bar(x, values, color=(colors * (len(values)//len(colors)+1))[:len(values)], width=.68)
            for bar, value in zip(bars, values):
                ax.annotate(f"{value:.2f}" if isinstance(value, float) else str(value), (bar.get_x()+bar.get_width()/2, bar.get_height()),
                            xytext=(0, 4), textcoords="offset points", ha="center", fontsize=8, color=C["muted"])
        if kind not in ("pie", "doughnut"):
            ax.set_title(title, loc="left", color=C["ink"], fontsize=11, pad=15)
            ax.set_ylabel(ylabel, color=C["muted"], fontsize=8)
            ax.set_xticks(x, [str(label)[:25] for label in labels], rotation=32 if len(labels)>5 else 0, ha="right" if len(labels)>5 else "center", fontsize=8)
            ax.tick_params(axis="y", labelsize=8, colors=C["muted"])
            ax.grid(axis="y", color=C["line"], linewidth=.8); ax.set_axisbelow(True)
            ax.spines[["top", "right", "left"]].set_visible(False)

    def _embed_chart(self, host, title, draw, figsize=(6.4, 3.1), replace=False):
        if replace:
            for child in host.winfo_children(): child.destroy()
        else:
            for child in host.winfo_children(): child.destroy()
        tk.Label(host, text=title, bg=C["surface"], fg=C["ink"], font=(FONT, 10, "bold")).pack(anchor="w", padx=13, pady=(10, 0))
        fig = Figure(figsize=figsize, dpi=100, facecolor=C["surface"])
        ax = fig.add_subplot(111)
        draw(ax)
        fig.tight_layout(pad=2.0)
        canvas = FigureCanvasTkAgg(fig, master=host)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=(0, 5))
        canvas.mpl_connect("motion_notify_event", lambda event: self._chart_hover(event, ax, canvas))
        if host is getattr(self, "studio_chart_host", None):
            toolbar = NavigationToolbar2Tk(canvas, host, pack_toolbar=False)
            toolbar.update(); toolbar.pack(side="bottom", fill="x")

    def _chart_hover(self, event, ax, canvas):
        if event.inaxes != ax or event.xdata is None or event.ydata is None:
            return
        if not hasattr(ax, "_hover_annot"):
            ax._hover_annot = ax.annotate("", xy=(0, 0), xytext=(10, 12), textcoords="offset points",
                                          bbox={"boxstyle": "round,pad=.4", "fc": C["nav"], "ec": "none"},
                                          color="white", fontsize=8, visible=False)
        annotation = ax._hover_annot
        found = False
        for patch in ax.patches:
            contains, _ = patch.contains(event)
            if contains:
                if hasattr(patch, "get_height") and hasattr(patch, "get_width"):
                    x, y, width, height = patch.get_x(), patch.get_y(), patch.get_width(), patch.get_height()
                    horizontal = width > height
                    index = round(y + height/2) if horizontal else round(x + width/2)
                    tick_labels = ax.get_yticklabels() if horizontal else ax.get_xticklabels()
                    label = tick_labels[index].get_text() if 0 <= index < len(tick_labels) else "Value"
                    value = width if horizontal else height
                    annotation.xy = (x + width if horizontal else x + width/2, y + height/2 if horizontal else y + height)
                    annotation.set_text(f"{label}: {value:,.3f}")
                else:
                    slice_index = list(ax.patches).index(patch)
                    legend = ax.get_legend()
                    slice_label = legend.get_texts()[slice_index].get_text() if legend and slice_index < len(legend.get_texts()) else "Category"
                    annotation.xy = event.xdata, event.ydata
                    annotation.set_text(f"{slice_label}: {(patch.theta2-patch.theta1)/360:.1%}")
                annotation.set_visible(True); found = True; break
        if not found:
            for line in ax.lines:
                xdata, ydata = line.get_xdata(), line.get_ydata()
                if len(xdata) == 0: continue
                points = ax.transData.transform(list(zip(xdata, ydata)))
                distances = ((points[:, 0]-event.x)**2 + (points[:, 1]-event.y)**2)**.5
                index = int(distances.argmin())
                if distances[index] < 11:
                    labels = ax.get_xticklabels()
                    category = labels[index].get_text() if index < len(labels) else str(index + 1)
                    annotation.xy = (xdata[index], ydata[index])
                    annotation.set_text(f"{category}: {ydata[index]:,.3f}")
                    annotation.set_visible(True); found = True; break
        if annotation.get_visible() != found or found:
            annotation.set_visible(found); canvas.draw_idle()

    # ------------------------------------------------------------- tables
    def _filtered_rules(self):
        if self.rule_data.empty:
            return pd.DataFrame()
        df = self.rule_data.drop_duplicates(["antecedents", "consequents"]).copy()
        method = self.rule_algorithm.get()
        if method in ("Apriori", "FP-Growth"):
            df = self.rule_data[self.rule_data["algorithm"].eq("apriori" if method == "Apriori" else "fpgrowth")].drop_duplicates(["antecedents", "consequents"])
        q = self.rule_search.get().strip().lower()
        if q and q != "filter by product…":
            df = df[df["antecedents"].str.lower().str.contains(q, na=False) | df["consequents"].str.lower().str.contains(q, na=False)]
        try:
            df = df[df["lift"] >= float(self.rule_min_lift.get() or 0)]
        except ValueError:
            pass
        return df

    def _refresh_rules(self, reset=False):
        if not hasattr(self, "rule_tree"):
            return
        if reset: self.rule_page = 0
        df = self._filtered_rules()
        if self.sort_column in df.columns and not df.empty:
            df = df.sort_values(self.sort_column, ascending=not self.sort_reverse, kind="stable")
        total = len(df)
        pages = max(1, (total + self.page_size - 1) // self.page_size)
        self.rule_page = min(self.rule_page, pages - 1)
        shown = df.iloc[self.rule_page*self.page_size:(self.rule_page+1)*self.page_size]
        self.rule_tree.delete(*self.rule_tree.get_children())
        for i, (_, r) in enumerate(shown.iterrows()):
            sources = self.rule_data.loc[(self.rule_data.antecedents == r.antecedents) & (self.rule_data.consequents == r.consequents), "algorithm"].unique()
            method = "Both" if len(sources) > 1 else ("FP-Growth" if r.algorithm == "fpgrowth" else "Apriori")
            self.rule_tree.insert("", "end", values=(method, r.antecedents, r.consequents, f"{r.support:.3f}", f"{r.confidence:.3f}", f"{r.lift:.3f}"), tags=("even" if i % 2 == 0 else "odd",))
        self.rule_count_label.configure(text=f"Showing {len(shown):,} of {total:,} rules · click a heading to sort")
        self.page_label.configure(text=f"Page {self.rule_page+1} of {pages}")
        self._configure_rule_columns()

    def _configure_rule_columns(self):
        if hasattr(self, "rule_tree"):
            self.rule_tree.configure(displaycolumns=self.visible_rule_columns)

    def _change_rule_page(self, delta):
        self.rule_page = max(0, self.rule_page + delta)
        self._refresh_rules()

    def _sort_rules(self, column):
        self.sort_reverse = not self.sort_reverse if self.sort_column == column else column in ("lift", "confidence", "support")
        self.sort_column = column
        self._refresh_rules()

    def _column_menu(self):
        menu = tk.Menu(self, tearoff=0)
        labels = {"algorithm":"Method", "antecedents":"Basket contains", "consequents":"Also likely", "support":"Support", "confidence":"Confidence", "lift":"Lift"}
        for column in labels:
            var = tk.BooleanVar(value=column in self.visible_rule_columns)
            menu.add_checkbutton(label=labels[column], variable=var,
                                 command=lambda c=column, v=var: self._toggle_column(c, v.get()))
        menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _toggle_column(self, column, shown):
        if shown and column not in self.visible_rule_columns: self.visible_rule_columns.append(column)
        if not shown and column in self.visible_rule_columns and len(self.visible_rule_columns) > 2: self.visible_rule_columns.remove(column)
        self._configure_rule_columns()

    def _refresh_itemsets(self):
        if not hasattr(self, "item_tree"): return
        self.item_tree.delete(*self.item_tree.get_children())
        df = self.itemset_data.copy()
        query = self.item_search.get().strip().lower() if hasattr(self, "item_search") else ""
        if query and query != "search itemsets…" and not df.empty:
            df = df[df.itemsets.str.lower().str.contains(query, na=False)]
        if not df.empty:
            sort_col = self.item_sort_column if self.item_sort_column in df.columns else "support"
            df = df.sort_values(sort_col, ascending=not self.item_sort_reverse, kind="stable")
            for i, (_, r) in enumerate(df.head(500).iterrows()):
                self.item_tree.insert("", "end", values=(r.itemsets, f"{r.support:.3f}", int(r.basket_count), int(r.size)), tags=("even" if i%2==0 else "odd",))

    def _sort_itemsets(self, col):
        if not self.itemset_data.empty and col in self.itemset_data:
            self.item_sort_reverse = not self.item_sort_reverse if self.item_sort_column == col else col in ("support", "basket_count", "size")
            self.item_sort_column = col
            self._refresh_itemsets()

    # ------------------------------------------------------ algorithm/reporting
    def _update_algorithm_page(self):
        for tree in (getattr(self, "algorithm_tree", None),):
            if tree: tree.delete(*tree.get_children())
        for row in self.comparison:
            name = "FP-Growth" if row["algorithm"] == "fpgrowth" else "Apriori"
            if hasattr(self, "algorithm_tree"):
                self.algorithm_tree.insert("", "end", values=(name, row["frequent_itemsets"], row["rules"], f"{row['runtime_seconds']:.6f}"))
        if self.comparison:
            a, b = self.comparison[0], self.comparison[1]
            for name, row in (("Apriori", a), ("FP-Growth", b)):
                detail = (f"{row['frequent_itemsets']:,} frequent itemsets\n{row['rules']:,} generated rules\n"
                          f"Runtime: {row['runtime_seconds']:.6f} sec\n"
                          f"Candidate search: {'level-wise pruning' if name == 'Apriori' else 'FP-tree pattern growth'}")
                self.algo_cards[name].configure(text=detail)
            self._embed_chart(self.algorithm_chart_host, "Elapsed time · lower is faster", self._draw_runtime, figsize=(8.4, 2.35), replace=True)

    def _draw_runtime(self, ax):
        labels = ["Apriori" if r["algorithm"] == "apriori" else "FP-Growth" for r in self.comparison]
        vals = [r["runtime_seconds"] for r in self.comparison]
        bars = ax.barh(labels, vals, color=[C["blue"], C["purple"]], height=.5)
        ax.set_xlabel("Seconds", color=C["muted"], fontsize=8)
        ax.grid(axis="x", color=C["line"]); ax.set_axisbelow(True); ax.spines[["top","right","left"]].set_visible(False)
        for b,v in zip(bars,vals): ax.text(v, b.get_y()+b.get_height()/2, f"  {v:.5f}s", va="center", fontsize=8, color=C["muted"])

    def _update_report_summary(self):
        if not hasattr(self, "report_summary"): return
        rules = self.rule_data.drop_duplicates(["antecedents", "consequents"]) if not self.rule_data.empty else self.rule_data
        self.report_summary.configure(text=f"Dataset: {self.data_path.get()}\nBaskets: {self.summary.get('transactions',0):,}   ·   Products: {self.summary.get('distinct_items',0):,}   ·   Average basket: {self.summary.get('average_basket_size',0):.2f} items\nThresholds: support {self.min_support.get()}   ·   confidence {self.min_confidence.get()}   ·   lift {self.min_lift.get()}\nFrequent itemsets: {len(self.itemset_data):,}   ·   Distinct rules: {len(rules):,}   ·   Algorithms: Apriori and FP-Growth")

    def _export_menu(self):
        menu = tk.Menu(self, tearoff=0, font=(FONT, 9))
        menu.add_command(label="Excel workbook (.xlsx)", command=lambda: self._export("xlsx"))
        menu.add_command(label="Rules table (.csv)", command=lambda: self._export("csv"))
        menu.add_command(label="PDF analysis report (.pdf)", command=lambda: self._export("pdf"))
        menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _export(self, kind):
        if not self.summary:
            messagebox.showinfo("No analysis to export", "Run an analysis first.", parent=self); return
        ext = {"xlsx":".xlsx", "csv":".csv", "pdf":".pdf"}[kind]
        path = filedialog.asksaveasfilename(title="Export analysis", initialdir=OUT, initialfile=f"basket_insights{ext}", defaultextension=ext,
                                           filetypes=((f"{kind.upper()} files", f"*{ext}"),))
        if not path: return
        try:
            if kind == "csv": self._export_csv(path)
            elif kind == "xlsx": self._export_xlsx(path)
            else: self._export_pdf(path)
            self.status.set(f"Exported {Path(path).name}")
            messagebox.showinfo("Export complete", f"Saved report to:\n{path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    def _export_csv(self, path):
        self._rules_for_export().to_csv(path, index=False)

    def _rules_for_export(self):
        rules = self._filtered_rules().copy()
        if rules.empty:
            return rules
        methods = []
        for _, row in rules.iterrows():
            sources = self.rule_data.loc[(self.rule_data.antecedents == row.antecedents) & (self.rule_data.consequents == row.consequents), "algorithm"].unique()
            methods.append("Both" if len(sources) > 1 else ("FP-Growth" if sources[0] == "fpgrowth" else "Apriori"))
        rules["algorithm"] = methods
        return rules

    def _export_xlsx(self, path):
        from openpyxl.styles import Font, PatternFill
        rules = self._rules_for_export()
        summary = pd.DataFrame([self.summary | {"min_support":self.min_support.get(), "min_confidence":self.min_confidence.get(), "min_lift":self.min_lift.get()}])
        compare = pd.DataFrame(self.comparison)
        items = self.itemset_data.copy()
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            rules.to_excel(writer, sheet_name="Association Rules", index=False)
            items.to_excel(writer, sheet_name="Frequent Itemsets", index=False)
            compare.to_excel(writer, sheet_name="Algorithm Comparison", index=False)
            summary.to_excel(writer, sheet_name="Dataset Summary", index=False)
            for ws in writer.book.worksheets:
                ws.freeze_panes = "A2"
                ws.auto_filter.ref = ws.dimensions
                for cell in ws[1]:
                    cell.font = Font(name="Aptos", bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor="173B58")
                for column in ws.columns:
                    letter = column[0].column_letter
                    ws.column_dimensions[letter].width = min(48, max(12, max(len(str(c.value or "")) for c in column) + 2))

    def _export_pdf(self, path):
        import tempfile
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as PDFImage, PageBreak
        from reportlab.lib.enums import TA_LEFT
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=7, leading=9, alignment=TA_LEFT))
        doc = SimpleDocTemplate(path, pagesize=landscape(letter), rightMargin=.45*inch, leftMargin=.45*inch, topMargin=.45*inch, bottomMargin=.5*inch)
        chart_path = None
        story = [Paragraph("Basket Insights | Executive Dashboard", styles["Title"]),
                 Paragraph(f"Dataset: {Path(self.data_path.get()).name} · {self.summary.get('transactions',0):,} baskets · {self.summary.get('distinct_items',0):,} products", styles["BodyText"]), Spacer(1, 8)]
        metrics = [["Baskets", "Products", "Avg. basket", "Frequent itemsets", "Distinct rules", "Best lift"],
                   [f"{self.summary.get('transactions',0):,}", f"{self.summary.get('distinct_items',0):,}", f"{self.summary.get('average_basket_size',0):.2f}", f"{len(self.itemset_data):,}", f"{len(self._filtered_rules()):,}", f"{self.rule_data.lift.max():.2f}×" if not self.rule_data.empty else "—"]]
        story += [Table(metrics, colWidths=[1.55*inch]*6, style=TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#173B58")), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("TEXTCOLOR",(0,1),(-1,1),colors.HexColor("#173B58")), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9), ("GRID",(0,0),(-1,-1),.35,colors.HexColor("#dbe4ed")), ("PADDING",(0,0),(-1,-1),7)])), Spacer(1, 8)]
        story += [Paragraph(f"Thresholds: support {self.min_support.get()} · confidence {self.min_confidence.get()} · lift {self.min_lift.get()}", styles["BodyText"]), Spacer(1, 8)]
        if not self.rule_data.empty:
            top = self.rule_data.sort_values(["lift", "support"], ascending=False).iloc[0]
            story += [Paragraph(f"Top insight: {top['antecedents']} → {top['consequents']} · support {top['support']:.1%} · confidence {top['confidence']:.1%} · lift {top['lift']:.2f}×", styles["BodyText"]), Spacer(1, 5)]
        # Recreate the six Overview visualizations in a single print-ready dashboard panel.
        report_figure = Figure(figsize=(12, 6.0), dpi=140, facecolor="white")
        FigureCanvasAgg(report_figure)
        chart_specs = [self._chart_products, self._chart_baskets, self._chart_rule_lift,
                       self._chart_rule_scatter, self._chart_runtime, self._chart_itemset_sizes]
        for i, (title, draw) in enumerate(zip(("Most purchased products", "Basket size distribution", "Top rules by lift", "Rule support vs confidence", "Algorithm runtime", "Frequent itemsets by size"), chart_specs)):
            ax = report_figure.add_subplot(2, 3, i + 1)
            ax.set_title(title, loc="left", fontsize=10, color=C["ink"], pad=7)
            draw(ax)
        report_figure.tight_layout(pad=2.2)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as chart_file:
            chart_path = chart_file.name
        report_figure.savefig(chart_path, dpi=140, facecolor="white", bbox_inches="tight")
        story += [PDFImage(chart_path, width=10.0*inch, height=5.0*inch), PageBreak(), Paragraph("Ranked association rules", styles["Heading2"])]
        rules = self._rules_for_export().sort_values(["lift","support"], ascending=False).head(40)
        data = [["Method", "Basket contains", "Also likely", "Support", "Confidence", "Lift"]]
        for _, r in rules.iterrows():
            sources = self.rule_data.loc[(self.rule_data.antecedents == r.antecedents)&(self.rule_data.consequents == r.consequents),"algorithm"].unique()
            method = "Both" if len(sources)>1 else sources[0]
            data.append([method, r.antecedents, r.consequents, f"{r.support:.3f}", f"{r.confidence:.3f}", f"{r.lift:.3f}"])
        table = Table(data, repeatRows=1, colWidths=[1.0*inch,2.5*inch,2.5*inch,.85*inch,1.0*inch,.7*inch])
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#173B58")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#dbe4ed")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f4f7fb")]),("FONTSIZE",(0,0),(-1,-1),8), ("VALIGN",(0,0),(-1,-1),"TOP"), ("PADDING",(0,0),(-1,-1),5)]))
        story += [table, Spacer(1, 12), Paragraph("Interpretation", styles["Heading2"]),
                  Paragraph("Confidence alone can overstate a rule when its consequent is already popular. Lift compares rule confidence with the consequent's baseline support. Rules describe co-purchase patterns; they do not prove causation. Results depend on the selected dataset and thresholds.", styles["BodyText"])]
        try:
            doc.build(story)
        finally:
            if chart_path and os.path.exists(chart_path):
                os.remove(chart_path)

    # --------------------------------------------------------------- controls
    def _global_search_changed(self):
        query = self.global_search.get().strip()
        if query and query != "Search rules or products":
            self.rule_search.set(query)
            self._show_page("Rules Explorer")
            self._refresh_rules(reset=True)

    def _clear_search_hint(self, _event):
        if self.global_search.get() == "Search rules or products":
            self.global_search.set("")

    def _clear_rule_hint(self, _event):
        if self.rule_search.get() == "Filter by product…": self.rule_search.set("")

    def _placeholder_clear(self, event, value):
        if event.widget.get() == value: event.widget.delete(0, "end")

    def _show_range_info(self):
        messagebox.showinfo("Available date range", "This basket file does not contain dates. The dashboard uses all available baskets and does not calculate time-based changes.", parent=self)

    def _notifications(self):
        if self.summary:
            messagebox.showinfo("Analysis status", f"Latest analysis contains {self.summary.get('transactions',0):,} baskets and {len(self._filtered_rules()):,} distinct rules.", parent=self)
        else:
            messagebox.showinfo("No analysis yet", "Import a transaction CSV and run the analysis to see dashboard insights.", parent=self)

    def _profile(self):
        messagebox.showinfo("Project profile", "Muhammad Usman Nazir\n24PWDSC0178\nDS-A38 · Association Rule Mining for Food Product Bundles", parent=self)

    def _open_output(self):
        os.startfile(OUT)


if __name__ == "__main__":
    BasketInsights().mainloop()
