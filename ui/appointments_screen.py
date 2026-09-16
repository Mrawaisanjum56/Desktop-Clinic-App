"""
appointments_screen.py — clinic_app_v6 (NEW)

The daily token-queue feature (core/appointment_manager.py) was added in
v5 but never had a screen — this gives it one. Add a patient to today's
queue, see who's waiting/in-progress/done, and jump straight into
recording their visit.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

from core.patient_manager import search_patients, get_patient_by_id
from core.appointment_manager import (
    add_appointment, get_queue_for_date, update_status,
    cancel_appointment, get_next_waiting, get_today_stats
)

STATUS_COLORS = {
    "waiting": "#fef9e7", "in-progress": "#eaf4fb",
    "done": "#eafaf1", "cancelled": "#fdedec",
}


class AppointmentsScreen(ctk.CTkFrame):
    def __init__(self, master, on_new_visit=None):
        super().__init__(master, fg_color="transparent")
        self.on_new_visit = on_new_visit
        self._selected_patient = None
        self._patient_listbox = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        title_frame = ctk.CTkFrame(self, fg_color="#b7791f", corner_radius=10)
        title_frame.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(title_frame, text="Today's Appointment Queue",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="white").pack(pady=12)

        # Add-to-queue row
        add_frame = ctk.CTkFrame(self, corner_radius=10)
        add_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(add_frame, text="Add Patient to Queue",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#b7791f").pack(anchor="w", padx=15, pady=(10, 5))

        row = ctk.CTkFrame(add_frame, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0, 4))

        self.search_entry = ctk.CTkEntry(row, placeholder_text="Search patient by name or phone...",
                                         height=36, font=ctk.CTkFont(size=13))
        self.search_entry.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", self._search_patients)

        ctk.CTkButton(row, text="+ Add to Queue", width=140, height=36,
                      fg_color="#b7791f", hover_color="#8a5a16",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._add_to_queue).pack(side="left")

        self.dropdown_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        self.dropdown_frame.pack(fill="x", padx=15)

        self.selected_label = ctk.CTkLabel(add_frame, text="No patient selected",
                                           font=ctk.CTkFont(size=12), text_color="#7f8c8d")
        self.selected_label.pack(anchor="w", padx=15, pady=(2, 10))

        # Stats
        self.stats_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12, weight="bold"),
                                        text_color="#1c2833")
        self.stats_label.pack(anchor="w", padx=20, pady=(0, 6))

        # Queue table
        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        hdr = ctk.CTkFrame(table_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(hdr, text="Queue", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#2c3e50").pack(side="left")
        ctk.CTkButton(hdr, text="Refresh", width=80, height=28,
                      fg_color="#566573", hover_color="#2c3e50",
                      font=ctk.CTkFont(size=11), command=self.refresh).pack(side="right")

        cols = ("Token", "Name", "Phone", "Status", "Start Visit", "Mark Done", "Cancel")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        widths = {"Token": 60, "Name": 200, "Phone": 130, "Status": 100,
                  "Start Visit": 90, "Mark Done": 90, "Cancel": 70}
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths[c], anchor="w" if c == "Name" else "center")

        style = ttk.Style()
        style.configure("Appt.Treeview", rowheight=30, font=("Helvetica", 11))
        self.tree.configure(style="Appt.Treeview")
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(status, background=color)

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        sb.pack(side="right", fill="y", pady=(0, 8))
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11))
        self.status_label.pack(pady=(0, 5))

    # ─────────────────────────────────────────────

    def _search_patients(self, event=None):
        q = self.search_entry.get().strip()
        self._hide_dropdown()
        if len(q) < 2:
            return
        results = search_patients(q)
        if not results:
            return
        lb = tk.Listbox(self.dropdown_frame, height=min(5, len(results)),
                        font=("Helvetica", 11), relief="flat",
                        selectbackground="#f5d7a3", activestyle="none")
        for r in results:
            lb.insert("end", f"{r['name']}  |  {r['phone']}  |  ID:{r['id']}")
        lb.pack(fill="x")
        lb.bind("<<ListboxSelect>>", lambda e: self._pick_patient(results, lb))
        self._patient_listbox = lb

    def _pick_patient(self, results, lb):
        idx = lb.curselection()
        if not idx:
            return
        self._selected_patient = results[idx[0]]
        self.selected_label.configure(
            text=f"  {self._selected_patient['name']}  |  {self._selected_patient['phone']}",
            text_color="#b7791f")
        self._hide_dropdown()
        self.search_entry.delete(0, "end")

    def _hide_dropdown(self):
        if self._patient_listbox:
            self._patient_listbox.destroy()
            self._patient_listbox = None

    def _add_to_queue(self):
        if not self._selected_patient:
            self._set_status("Search for and select a patient first.", error=True)
            return
        appt_id = add_appointment(self._selected_patient["id"])
        self._set_status(f"\u2714  Added to queue.", error=False)
        self._selected_patient = None
        self.selected_label.configure(text="No patient selected", text_color="#7f8c8d")
        self.refresh()

    # ─────────────────────────────────────────────

    def refresh(self):
        stats = get_today_stats()
        self.stats_label.configure(
            text=f"Total: {stats['total']}   |   Waiting: {stats['waiting']}   |   "
                 f"In Progress: {stats['in-progress']}   |   Done: {stats['done']}   |   "
                 f"Cancelled: {stats['cancelled']}"
        )
        for row in self.tree.get_children():
            self.tree.delete(row)
        for appt in get_queue_for_date():
            self.tree.insert("", "end", iid=str(appt["id"]), values=(
                appt["token_no"], appt["patient_name"], appt["phone"],
                appt["status"].title(),
                "Start" if appt["status"] == "waiting" else "—",
                "Done" if appt["status"] in ("waiting", "in-progress") else "—",
                "Cancel" if appt["status"] in ("waiting", "in-progress") else "—",
            ), tags=(appt["status"],))

    def _on_tree_click(self, event):
        col = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        appt_id = int(row_id)
        vals = self.tree.item(row_id, "values")
        status = vals[3].lower()

        if col == "#5" and status == "waiting":   # Start Visit
            update_status(appt_id, "in-progress")
            patient_id = self._patient_id_for_row(vals)
            self.refresh()
            if patient_id and self.on_new_visit:
                patient = get_patient_by_id(patient_id)
                if patient:
                    self.on_new_visit(patient)

        elif col == "#6" and status in ("waiting", "in-progress"):   # Mark Done
            update_status(appt_id, "done")
            self._set_status("Marked as done.", error=False)
            self.refresh()

        elif col == "#7" and status in ("waiting", "in-progress"):   # Cancel
            if messagebox.askyesno("Cancel Appointment", "Remove this patient from today's queue?"):
                cancel_appointment(appt_id)
                self._set_status("Appointment cancelled.", error=False)
                self.refresh()

    def _patient_id_for_row(self, vals):
        """Look up the patient by name+phone shown in the row (queue
        rows don't carry patient_id directly in the tree values)."""
        name, phone = vals[1], vals[2]
        for appt in get_queue_for_date():
            if appt["patient_name"] == name and appt["phone"] == phone:
                return appt["patient_id"]
        return None

    def _set_status(self, msg, error=False):
        self.status_label.configure(text=msg, text_color="#e74c3c" if error else "#8a5a16")
