"""
search_screen.py — clinic_app_v6

Ported from clinic_app_v4. Changes for the v5/v6 schema:
  - get_today_patients()/get_visits_by_patient()/get_bills_by_patient()
    don't exist anymore — replaced with patient_manager.get_all_patients()
    (there's no "registered today" concept without created_at filtering,
    so this lists everyone, most recent first, and search narrows it)
    and patient_manager.get_patient_full_history() for the detail panel.
  - Dropped the Department/Doctor columns (schema no longer has them).
  - Bill columns renamed: total -> total_amount, created_at -> bill_date.
  - Added "New Visit" (record another visit for this patient) alongside
    the existing "Create Bill" action, and a "Reprint Prescription"
    button for any past visit that has one.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from core.patient_manager import search_patients, get_all_patients, get_patient_full_history
from reports.pdf_generator import generate_prescription_pdf, open_pdf


class SearchScreen(ctk.CTkFrame):
    def __init__(self, master, on_bill_patient=None, on_new_visit=None):
        super().__init__(master, fg_color="transparent")
        self.on_bill_patient = on_bill_patient
        self.on_new_visit = on_new_visit
        self._visits_cache = []
        self._build_ui()
        self._load_all()

    def _build_ui(self):
        title_frame = ctk.CTkFrame(self, fg_color="#1a5276", corner_radius=10)
        title_frame.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(title_frame, text="Patient Search & History",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="white").pack(pady=12)

        search_frame = ctk.CTkFrame(self, corner_radius=10)
        search_frame.pack(fill="x", padx=10, pady=10)

        row = ctk.CTkFrame(search_frame, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=12)

        self.search_entry = ctk.CTkEntry(row, placeholder_text="Search by name, phone, or CNIC...",
                                         height=38, font=ctk.CTkFont(size=13))
        self.search_entry.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        ctk.CTkButton(row, text="Show All", height=38, width=120,
                      fg_color="#1a5276", hover_color="#154360",
                      command=self._load_all).pack(side="left")

        left_panel = ctk.CTkFrame(self, corner_radius=10)
        left_panel.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.count_label = ctk.CTkLabel(left_panel, text="",
                                        font=ctk.CTkFont(size=11), text_color="#7f8c8d")
        self.count_label.pack(anchor="w", padx=12, pady=(8, 2))

        cols = ("ID", "Name", "Age", "Phone", "Gender", "CNIC", "Address")
        self.patient_tree = ttk.Treeview(left_panel, columns=cols, show="headings", height=8)
        widths = {"ID": 45, "Name": 170, "Age": 50, "Phone": 120, "Gender": 65,
                  "CNIC": 130, "Address": 160}
        for c in cols:
            self.patient_tree.heading(c, text=c)
            self.patient_tree.column(c, width=widths[c], anchor="center" if c != "Name" else "w")

        style = ttk.Style()
        style.configure("Search.Treeview", rowheight=28, font=("Helvetica", 11))
        self.patient_tree.configure(style="Search.Treeview")

        sb = ttk.Scrollbar(left_panel, orient="vertical", command=self.patient_tree.yview)
        self.patient_tree.configure(yscrollcommand=sb.set)
        self.patient_tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        sb.pack(side="right", fill="y", pady=(0, 8))
        self.patient_tree.bind("<<TreeviewSelect>>", self._on_patient_select)

        detail_frame = ctk.CTkFrame(self, corner_radius=10)
        detail_frame.pack(fill="x", padx=10, pady=(0, 10))

        header_row = ctk.CTkFrame(detail_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(header_row, text="Patient Detail",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#1a5276").pack(side="left")

        self.reprint_btn = ctk.CTkButton(
            header_row, text="Reprint Prescription", width=170, height=34,
            fg_color="#0f8b8d", hover_color="#0b6668",
            command=self._reprint_prescription,
            font=ctk.CTkFont(size=12, weight="bold"), state="disabled")
        self.reprint_btn.pack(side="right", padx=(6, 0))

        self.visit_btn = ctk.CTkButton(
            header_row, text="New Visit", width=140, height=34,
            fg_color="#1a5276", hover_color="#154360",
            command=self._open_new_visit,
            font=ctk.CTkFont(size=12, weight="bold"), state="disabled")
        self.visit_btn.pack(side="right", padx=(6, 0))

        self.bill_btn = ctk.CTkButton(
            header_row, text="Create Bill", width=140, height=34,
            fg_color="#7d3c98", hover_color="#5b2c6f",
            command=self._open_billing,
            font=ctk.CTkFont(size=12, weight="bold"), state="disabled")
        self.bill_btn.pack(side="right")

        detail_cols = ctk.CTkFrame(detail_frame, fg_color="transparent")
        detail_cols.pack(fill="x", padx=15, pady=(0, 12))

        vf = ctk.CTkFrame(detail_cols, corner_radius=8)
        vf.pack(side="left", expand=True, fill="both", padx=(0, 8))
        ctk.CTkLabel(vf, text="Visit History (select a row to reprint)",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=(6, 2))
        vcols = ("Date", "Diagnosis", "Rx")
        self.visit_tree = ttk.Treeview(vf, columns=vcols, show="headings", height=4)
        self.visit_tree.heading("Date", text="Date")
        self.visit_tree.heading("Diagnosis", text="Diagnosis")
        self.visit_tree.heading("Rx", text="Rx")
        self.visit_tree.column("Date", width=130)
        self.visit_tree.column("Diagnosis", width=220)
        self.visit_tree.column("Rx", width=40, anchor="center")
        self.visit_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.visit_tree.bind("<<TreeviewSelect>>", self._on_visit_select)

        bf = ctk.CTkFrame(detail_cols, corner_radius=8)
        bf.pack(side="left", fill="both")
        ctk.CTkLabel(bf, text="Billing History",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=(6, 2))
        bcols = ("Bill #", "Total (Rs.)", "Date")
        self.bill_tree = ttk.Treeview(bf, columns=bcols, show="headings", height=4)
        for c in bcols:
            self.bill_tree.heading(c, text=c)
            self.bill_tree.column(c, width=90, anchor="center")
        self.bill_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._selected_patient_id = None
        self._selected_patient = None
        self._selected_visit_id = None

    def _load_all(self):
        self.search_entry.delete(0, "end")
        patients = get_all_patients()
        self._populate_table(patients)
        self.count_label.configure(text=f"All patients: {len(patients)}")

    def _on_search(self, event=None):
        q = self.search_entry.get().strip()
        if not q:
            self._load_all()
            return
        results = search_patients(q)
        self._populate_table(results)
        self.count_label.configure(text=f"{len(results)} result(s)")

    def _populate_table(self, patients):
        for row in self.patient_tree.get_children():
            self.patient_tree.delete(row)
        for p in patients:
            self.patient_tree.insert("", "end", iid=str(p["id"]),
                                     values=(p["id"], p["name"], p["age"],
                                             p["phone"], p["gender"],
                                             p.get("cnic", "") or "—",
                                             p.get("address", "") or "—"))

    def _on_patient_select(self, event=None):
        sel = self.patient_tree.selection()
        if not sel:
            return
        patient_id = int(sel[0])
        self._selected_patient_id = patient_id
        self.bill_btn.configure(state="normal")
        self.visit_btn.configure(state="normal")
        self._load_patient_detail(patient_id)

    def _load_patient_detail(self, patient_id):
        for row in self.visit_tree.get_children():
            self.visit_tree.delete(row)
        for row in self.bill_tree.get_children():
            self.bill_tree.delete(row)
        self.reprint_btn.configure(state="disabled")
        self._selected_visit_id = None

        history = get_patient_full_history(patient_id)
        self._selected_patient = history["patient"]
        self._visits_cache = history["visits"]

        for entry in history["visits"]:
            v = entry["visit"]
            rx_count = len(entry["prescriptions"])
            self.visit_tree.insert("", "end", iid=str(v["id"]),
                                   values=(str(v["visit_date"])[:16],
                                           (v.get("diagnosis") or "—")[:60],
                                           rx_count if rx_count else "—"))

        for b in history["bills"]:
            self.bill_tree.insert("", "end",
                                  values=(b["id"], f"{b['total_amount']:.0f}",
                                          str(b["bill_date"])[:10]))

    def _on_visit_select(self, event=None):
        sel = self.visit_tree.selection()
        if not sel:
            self.reprint_btn.configure(state="disabled")
            self._selected_visit_id = None
            return
        self._selected_visit_id = int(sel[0])
        self.reprint_btn.configure(state="normal")

    def _reprint_prescription(self):
        if not self._selected_visit_id:
            return
        entry = next((e for e in self._visits_cache if e["visit"]["id"] == self._selected_visit_id), None)
        if not entry:
            return
        try:
            filepath = generate_prescription_pdf(
                self._selected_visit_id, self._selected_patient,
                entry["visit"], entry["prescriptions"])
            open_pdf(filepath)
        except Exception as e:
            messagebox.showerror("PDF Error", f"Could not generate prescription:\n\n{e}")

    def _open_billing(self):
        if self._selected_patient_id and self.on_bill_patient:
            self.on_bill_patient(self._selected_patient)

    def _open_new_visit(self):
        if self._selected_patient_id and self.on_new_visit:
            self.on_new_visit(self._selected_patient)

    def refresh(self):
        self._load_all()
