"""
dashboard.py — clinic_app_v6

Rebuilt from clinic_app_v4's dashboard. The old version showed
Male/Female/Department/Doctor breakdowns, which relied on the
patient_type/doctor_id columns that no longer exist in the v5/v6 schema
(this clinic app is single-doctor; that concept was dropped when the
schema was redesigned). Replaced with what the new schema actually
tracks: today's visits, today's revenue, the token queue, and
stock/expiry alerts — all sourced from the real v6 managers.
"""

import customtkinter as ctk
from tkinter import ttk
from datetime import datetime, date

from core.billing_manager import get_today_summary
from core.medicine_manager import get_low_stock_medicines, get_expiring_medicines, get_expired_medicines
from core.appointment_manager import get_today_stats, get_queue_for_date
from core.patient_manager import get_all_patients


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, master, on_navigate=None):
        super().__init__(master, fg_color="transparent")
        self.on_navigate = on_navigate
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="#1c2833", corner_radius=10)
        header.pack(fill="x", padx=10, pady=(10, 0))

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="x", padx=20, pady=14)

        self.date_label = ctk.CTkLabel(
            header_inner, text="", font=ctk.CTkFont(size=13), text_color="#aeb6bf"
        )
        self.date_label.pack(side="right")

        ctk.CTkLabel(
            header_inner, text="Today's Overview",
            font=ctk.CTkFont(size=20, weight="bold"), text_color="white"
        ).pack(side="left")

        # Stats cards row
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.pack(fill="x", padx=10, pady=10)

        self.cards_frame2 = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame2.pack(fill="x", padx=10, pady=(0, 10))

        # Quick actions
        actions_frame = ctk.CTkFrame(self, corner_radius=10)
        actions_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(actions_frame, text="Quick Actions",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#1c2833").pack(anchor="w", padx=15, pady=(10, 8))

        btn_row = ctk.CTkFrame(actions_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(0, 12))

        actions = [
            ("+ New Patient", "#1a5276", "New Patient"),
            ("Search Patient", "#1a5276", "Search / History"),
            ("Today's Queue", "#b7791f", "Appointments"),
            ("Create Bill", "#7d3c98", "Billing"),
            ("Manage Medicines", "#145a32", "Medicines"),
        ]
        for label, color, nav in actions:
            ctk.CTkButton(
                btn_row, text=label, height=44, width=160,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=color,
                command=lambda n=nav: self.on_navigate(n) if self.on_navigate else None
            ).pack(side="left", padx=(0, 10))

        # Today's queue table
        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        table_header = ctk.CTkFrame(table_frame, fg_color="transparent")
        table_header.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(table_header, text="Today's Queue",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#1c2833").pack(side="left")
        ctk.CTkButton(table_header, text="Refresh", width=80, height=28,
                      fg_color="#566573", hover_color="#2c3e50",
                      font=ctk.CTkFont(size=11),
                      command=self.refresh).pack(side="right")

        cols = ("Token", "Name", "Phone", "Status", "Time")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=9)
        widths = {"Token": 60, "Name": 220, "Phone": 140, "Status": 110, "Time": 100}
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths[c],
                             anchor="center" if c not in ("Name",) else "w")

        style = ttk.Style()
        style.configure("Dash.Treeview", rowheight=28, font=("Helvetica", 11))
        style.configure("Dash.Treeview.Heading", font=("Helvetica", 11, "bold"))
        self.tree.configure(style="Dash.Treeview")
        self.tree.tag_configure("waiting", background="#fef9e7")
        self.tree.tag_configure("done", background="#eafaf1")
        self.tree.tag_configure("cancelled", background="#fdedec")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        sb.pack(side="right", fill="y", pady=(0, 8))

    def _make_stat_card(self, parent, title, value, subtitle, color, text_color="white"):
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color=color)
        card.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11),
                     text_color=text_color, fg_color="transparent").pack(anchor="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(card, text=str(value), font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=text_color, fg_color="transparent").pack(anchor="w", padx=14, pady=(2, 0))
        ctk.CTkLabel(card, text=subtitle, font=ctk.CTkFont(size=10),
                     text_color=text_color, fg_color="transparent").pack(anchor="w", padx=14, pady=(0, 10))
        return card

    def refresh(self):
        now = datetime.now()
        self.date_label.configure(text=now.strftime("%A, %d %B %Y   %I:%M %p"))

        for w in self.cards_frame.winfo_children():
            w.destroy()
        for w in self.cards_frame2.winfo_children():
            w.destroy()

        today_summary = get_today_summary()
        queue_stats = get_today_stats()
        low_stock = get_low_stock_medicines()
        expiring = get_expiring_medicines()
        expired = get_expired_medicines()
        total_patients = len(get_all_patients())

        # Row 1 — queue + patients
        self._make_stat_card(self.cards_frame, "Today's Visits",
                             today_summary["visits"], "Recorded today", "#1a5276")
        self._make_stat_card(self.cards_frame, "In Queue Today",
                             queue_stats["total"], "Tokens issued today", "#b7791f")
        self._make_stat_card(self.cards_frame, "Waiting",
                             queue_stats["waiting"], "Not yet seen", "#8a5a16")
        self._make_stat_card(self.cards_frame, "Done",
                             queue_stats["done"], "Seen today", "#1e8449")
        self._make_stat_card(self.cards_frame, "Total Patients",
                             total_patients, "Registered (all time)", "#566573")

        # Row 2 — revenue + stock alerts
        self._make_stat_card(self.cards_frame2, "Today's Revenue",
                             f"Rs. {today_summary['revenue']:,.0f}",
                             "From bills today", "#1e8449")

        low_color = "#c0392b" if len(low_stock) > 0 else "#1e8449"
        self._make_stat_card(self.cards_frame2, "Low Stock",
                             len(low_stock), "Medicines running low", low_color)

        exp_color = "#c0392b" if len(expiring) > 0 else "#1e8449"
        self._make_stat_card(self.cards_frame2, "Expiring Soon",
                             len(expiring), "Within alert window", exp_color)

        expd_color = "#922b21" if len(expired) > 0 else "#1e8449"
        self._make_stat_card(self.cards_frame2, "Expired",
                             len(expired), "Past expiry date", expd_color)

        # Populate today's queue table
        for row in self.tree.get_children():
            self.tree.delete(row)
        for appt in get_queue_for_date():
            time_str = str(appt["created_at"])[11:16] if appt.get("created_at") else ""
            self.tree.insert("", "end", values=(
                appt["token_no"], appt["patient_name"], appt["phone"],
                appt["status"].title(), time_str
            ), tags=(appt["status"],))
