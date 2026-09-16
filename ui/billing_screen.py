"""
billing_screen.py — clinic_app_v6

Ported from clinic_app_v4. The v5/v6 schema unified medicine and service
line items into one generic bill_items table (item_type/item_id/item_name)
instead of v4's separate bill_items + bill_service_items tables, so the
bill-building logic below merges both into one list before calling
billing_manager.create_bill(). Field names updated to match: stock_qty
(was quantity), total_amount (was total), and the bill needs an
attached visit_id — an empty visit is created for billing-only visits,
same as v4 did via log_visit(..., diagnosis="").
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

from core.medicine_manager import get_all_medicines
from core.service_manager import get_all_services
from core.patient_manager import search_patients
from core.billing_manager import create_bill, get_bill_by_id, get_bill_items
from core.visit_manager import add_visit
from reports.pdf_generator import generate_bill_pdf, open_pdf


class BillingScreen(ctk.CTkFrame):
    def __init__(self, master, prefill_patient=None):
        super().__init__(master, fg_color="transparent")
        self.bill_rows = []          # medicine rows
        self.service_rows = []       # service rows
        self.all_medicines = get_all_medicines()
        self.all_services = get_all_services()
        self.selected_patient = prefill_patient
        self._selected_medicine = None
        self._selected_service = None
        self._med_listbox = None
        self._svc_listbox = None
        self.patient_listbox = None
        self._build_ui()
        if prefill_patient:
            self._set_patient_display(prefill_patient)

    # ─────────────────────────── UI BUILD ────────────────────────────────

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=0)
        self.grid_columnconfigure(0, weight=1)

        title_frame = ctk.CTkFrame(self, fg_color="#7d3c98", corner_radius=10)
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        ctk.CTkLabel(
            title_frame, text="Patient Billing",
            font=ctk.CTkFont(size=18, weight="bold"), text_color="white"
        ).pack(pady=12)

        pat_frame = ctk.CTkFrame(self, corner_radius=10)
        pat_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkLabel(
            pat_frame, text="Patient",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#7d3c98"
        ).pack(anchor="w", padx=15, pady=(10, 5))

        ps_row = ctk.CTkFrame(pat_frame, fg_color="transparent")
        ps_row.pack(fill="x", padx=15, pady=(0, 4))

        self.patient_search = ctk.CTkEntry(
            ps_row, placeholder_text="Search patient by name or phone...",
            height=36, font=ctk.CTkFont(size=13)
        )
        self.patient_search.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.patient_search.bind("<KeyRelease>", self._search_patients)

        ctk.CTkButton(
            ps_row, text="Clear Patient", width=120, height=36,
            fg_color="#7f8c8d", hover_color="#5d6d7e",
            command=self._clear_patient
        ).pack(side="left")

        self.patient_dropdown_frame = ctk.CTkFrame(pat_frame, fg_color="transparent")
        self.patient_dropdown_frame.pack(fill="x", padx=15)

        self.patient_info_label = ctk.CTkLabel(
            pat_frame, text="No patient selected",
            font=ctk.CTkFont(size=12), text_color="#7f8c8d"
        )
        self.patient_info_label.pack(anchor="w", padx=15, pady=(2, 10))

        add_outer = ctk.CTkFrame(self, corner_radius=10)
        add_outer.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

        tab_bar = ctk.CTkFrame(add_outer, fg_color="transparent")
        tab_bar.pack(fill="x", padx=15, pady=(10, 0))

        self._tab_med_btn = ctk.CTkButton(
            tab_bar, text="Add Medicine", width=180, height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#7d3c98", hover_color="#5b2c6f",
            command=lambda: self._switch_tab("medicine")
        )
        self._tab_med_btn.pack(side="left", padx=(0, 6))

        self._tab_svc_btn = ctk.CTkButton(
            tab_bar, text="Add Service", width=180, height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#7f8c8d", hover_color="#5d6d7e",
            command=lambda: self._switch_tab("service")
        )
        self._tab_svc_btn.pack(side="left")

        self._med_panel = ctk.CTkFrame(add_outer, fg_color="transparent")
        self._med_panel.pack(fill="x", padx=15, pady=(6, 0))

        med_row = ctk.CTkFrame(self._med_panel, fg_color="transparent")
        med_row.pack(fill="x")

        mf = ctk.CTkFrame(med_row, fg_color="transparent")
        mf.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(mf, text="Medicine", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.med_search_entry = ctk.CTkEntry(mf, placeholder_text="Type to search medicine...", height=36)
        self.med_search_entry.pack(fill="x", pady=(2, 0))
        self.med_search_entry.bind("<KeyRelease>", self._filter_medicines)

        qf = ctk.CTkFrame(med_row, fg_color="transparent")
        qf.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(qf, text="Qty", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.qty_entry = ctk.CTkEntry(qf, placeholder_text="1", height=36, width=70)
        self.qty_entry.pack(pady=(2, 0))

        ctk.CTkButton(
            med_row, text="+ Add", width=90, height=36,
            fg_color="#7d3c98", hover_color="#5b2c6f",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._add_medicine_to_bill
        ).pack(side="left", pady=(16, 0))

        self.med_listbox_frame = ctk.CTkFrame(self._med_panel, fg_color="transparent")
        self.med_listbox_frame.pack(fill="x", pady=(2, 6))

        self._svc_panel = ctk.CTkFrame(add_outer, fg_color="transparent")
        svc_row = ctk.CTkFrame(self._svc_panel, fg_color="transparent")
        svc_row.pack(fill="x", padx=0, pady=(6, 0))

        sf = ctk.CTkFrame(svc_row, fg_color="transparent")
        sf.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(sf, text="Service", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.svc_search_entry = ctk.CTkEntry(sf, placeholder_text="Type to search service...", height=36)
        self.svc_search_entry.pack(fill="x", pady=(2, 0))
        self.svc_search_entry.bind("<KeyRelease>", self._filter_services)

        pf2 = ctk.CTkFrame(svc_row, fg_color="transparent")
        pf2.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(pf2, text="Price (Rs.)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.svc_price_entry = ctk.CTkEntry(pf2, placeholder_text="auto", height=36, width=100)
        self.svc_price_entry.pack(pady=(2, 0))

        ctk.CTkButton(
            svc_row, text="+ Add", width=90, height=36,
            fg_color="#c0392b", hover_color="#922b21",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._add_service_to_bill
        ).pack(side="left", pady=(16, 0))

        self.svc_listbox_frame = ctk.CTkFrame(self._svc_panel, fg_color="transparent")
        self.svc_listbox_frame.pack(fill="x", pady=(2, 6))

        table_container = ctk.CTkFrame(self, corner_radius=10)
        table_container.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 6))
        table_container.grid_rowconfigure(1, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            table_container, text="Bill Items",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#2c3e50"
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

        cols = ("#", "Type", "Item", "Qty", "Unit Price (Rs.)", "Total (Rs.)", "Remove")
        self.bill_tree = ttk.Treeview(table_container, columns=cols, show="headings", height=8)
        widths = {"#": 30, "Type": 75, "Item": 195, "Qty": 45,
                  "Unit Price (Rs.)": 120, "Total (Rs.)": 105, "Remove": 70}
        for c in cols:
            self.bill_tree.heading(c, text=c)
            self.bill_tree.column(c, width=widths[c], anchor="w" if c == "Item" else "center")

        style = ttk.Style()
        style.configure("Bill.Treeview", rowheight=30, font=("Helvetica", 11))
        style.configure("Bill.Treeview.Heading", font=("Helvetica", 11, "bold"))
        self.bill_tree.configure(style="Bill.Treeview")
        self.bill_tree.tag_configure("medicine", background="#eaf4fb")
        self.bill_tree.tag_configure("service", background="#fef9e7")

        self.bill_tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        sb2 = ttk.Scrollbar(table_container, orient="vertical", command=self.bill_tree.yview)
        sb2.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        self.bill_tree.configure(yscrollcommand=sb2.set)
        self.bill_tree.bind("<ButtonRelease-1>", self._on_bill_click)

        bottom = ctk.CTkFrame(self, fg_color="transparent", height=78)
        bottom.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 8))
        bottom.grid_propagate(False)
        bottom.grid_columnconfigure(0, weight=1)

        self.total_label = ctk.CTkLabel(
            bottom, text="Grand Total:  Rs. 0.00",
            font=ctk.CTkFont(size=20, weight="bold"), text_color="#7d3c98"
        )
        self.total_label.grid(row=0, column=0, sticky="w", padx=10)

        btn_wrap = ctk.CTkFrame(bottom, fg_color="transparent")
        btn_wrap.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            btn_wrap, text="Clear Bill", height=54, width=130,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#7f8c8d", hover_color="#5d6d7e",
            command=self._clear_bill
        ).pack(side="right")

        ctk.CTkButton(
            btn_wrap, text="Generate Bill & Print", height=54, width=210,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#1a5276", hover_color="#154360",
            command=self._finalize_bill
        ).pack(side="right", padx=(0, 10))

        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11))
        self.status_label.grid(row=5, column=0, sticky="ew", pady=(0, 4))

        self._switch_tab("medicine")

    # ─────────────────────────── TAB SWITCHING ───────────────────────────

    def _switch_tab(self, tab):
        if tab == "medicine":
            self._tab_med_btn.configure(fg_color="#7d3c98")
            self._tab_svc_btn.configure(fg_color="#7f8c8d")
            self._svc_panel.pack_forget()
            self._med_panel.pack(fill="x", padx=15, pady=(6, 0))
        else:
            self._tab_svc_btn.configure(fg_color="#c0392b")
            self._tab_med_btn.configure(fg_color="#7f8c8d")
            self._med_panel.pack_forget()
            self._svc_panel.pack(fill="x", padx=15, pady=(6, 0))

    # ─────────────────────────── PATIENT ─────────────────────────────────

    def _search_patients(self, event=None):
        q = self.patient_search.get().strip()
        if len(q) < 2:
            self._hide_patient_list()
            return
        self._show_patient_list(search_patients(q))

    def _show_patient_list(self, results):
        self._hide_patient_list()
        if not results:
            return
        lb = tk.Listbox(
            self.patient_dropdown_frame, height=min(5, len(results)),
            font=("Helvetica", 11), relief="flat",
            selectbackground="#d2b4de", activestyle="none"
        )
        for r in results:
            lb.insert("end", f"{r['name']}  |  {r['phone']}  |  ID:{r['id']}")
        lb.pack(fill="x")
        lb.bind("<<ListboxSelect>>", lambda e: self._pick_patient(results, lb))
        self.patient_listbox = lb

    def _pick_patient(self, results, lb):
        idx = lb.curselection()
        if not idx:
            return
        self._set_patient_display(results[idx[0]])
        self._hide_patient_list()
        self.patient_search.delete(0, "end")

    def _hide_patient_list(self):
        if self.patient_listbox:
            self.patient_listbox.destroy()
            self.patient_listbox = None

    def _set_patient_display(self, p):
        self.selected_patient = p
        self.patient_info_label.configure(
            text=f"  {p['name']}   |   Age: {p['age']}   |   {p['phone']}   |   ID: {p['id']}",
            text_color="#1a5276"
        )

    def _clear_patient(self):
        self.selected_patient = None
        self.patient_info_label.configure(text="No patient selected", text_color="#7f8c8d")

    # ─────────────────────────── MEDICINE ────────────────────────────────

    def _filter_medicines(self, event=None):
        q = self.med_search_entry.get().strip()
        self._hide_med_list()
        if not q:
            return
        results = [m for m in self.all_medicines if q.lower() in m["name"].lower()]
        if not results:
            return
        lb = tk.Listbox(
            self.med_listbox_frame, height=min(5, len(results)),
            font=("Helvetica", 11), relief="flat",
            selectbackground="#d2b4de", activestyle="none"
        )
        for m in results:
            lb.insert("end", f"{m['name']}  —  Rs. {m['price']:.2f}/{m['unit']}  [stock: {m['stock_qty']}]")
        lb.pack(fill="x")
        lb.bind("<<ListboxSelect>>", lambda e: self._pick_medicine(results, lb))
        self._med_listbox = lb

    def _pick_medicine(self, results, lb):
        idx = lb.curselection()
        if not idx:
            return
        self._selected_medicine = results[idx[0]]
        self.med_search_entry.delete(0, "end")
        self.med_search_entry.insert(0, self._selected_medicine["name"])
        self._hide_med_list()

    def _hide_med_list(self):
        if self._med_listbox:
            self._med_listbox.destroy()
            self._med_listbox = None

    def _add_medicine_to_bill(self):
        if not self._selected_medicine:
            self._set_status("Select a medicine first.", error=True)
            return
        qty_str = self.qty_entry.get().strip() or "1"
        try:
            qty = int(qty_str)
            if qty <= 0:
                raise ValueError
        except ValueError:
            self._set_status("Quantity must be a positive whole number.", error=True)
            return

        med = self._selected_medicine
        if med["stock_qty"] < qty:
            self._set_status(f"Only {med['stock_qty']} in stock.", error=True)
            return

        for row in self.bill_rows:
            if row["medicine_id"] == med["id"]:
                row["qty"] += qty
                self._refresh_bill_table()
                self._selected_medicine = None
                self.med_search_entry.delete(0, "end")
                self.qty_entry.delete(0, "end")
                return

        self.bill_rows.append({
            "medicine_id": med["id"], "name": med["name"], "unit": med["unit"],
            "qty": qty, "unit_price": med["price"],
        })
        self._refresh_bill_table()
        self._selected_medicine = None
        self.med_search_entry.delete(0, "end")
        self.qty_entry.delete(0, "end")
        self._set_status("", error=False)

    # ─────────────────────────── SERVICE ─────────────────────────────────

    def _filter_services(self, event=None):
        q = self.svc_search_entry.get().strip()
        self._hide_svc_list()
        results = self.all_services if not q else [
            s for s in self.all_services if q.lower() in s["name"].lower()]
        if not results:
            return
        lb = tk.Listbox(
            self.svc_listbox_frame, height=min(6, len(results)),
            font=("Helvetica", 11), relief="flat",
            selectbackground="#f9d5c0", activestyle="none"
        )
        for s in results:
            lb.insert("end", f"{s['name']}  —  Rs. {s['price']:.2f}")
        lb.pack(fill="x")
        lb.bind("<<ListboxSelect>>", lambda e: self._pick_service(results, lb))
        self._svc_listbox = lb

    def _pick_service(self, results, lb):
        idx = lb.curselection()
        if not idx:
            return
        self._selected_service = results[idx[0]]
        self.svc_search_entry.delete(0, "end")
        self.svc_search_entry.insert(0, self._selected_service["name"])
        self.svc_price_entry.delete(0, "end")
        self.svc_price_entry.insert(0, f"{self._selected_service['price']:.2f}")
        self._hide_svc_list()

    def _hide_svc_list(self):
        if self._svc_listbox:
            self._svc_listbox.destroy()
            self._svc_listbox = None

    def _add_service_to_bill(self):
        if not self._selected_service:
            self._set_status("Select a service first.", error=True)
            return
        price_str = self.svc_price_entry.get().strip()
        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            self._set_status("Enter a valid price for the service.", error=True)
            return

        self.service_rows.append({
            "service_id": self._selected_service["id"],
            "service_name": self._selected_service["name"],
            "price": price,
        })
        self._refresh_bill_table()
        self._selected_service = None
        self.svc_search_entry.delete(0, "end")
        self.svc_price_entry.delete(0, "end")
        self._set_status("", error=False)

    # ─────────────────────────── BILL TABLE ──────────────────────────────

    def _refresh_bill_table(self):
        for row in self.bill_tree.get_children():
            self.bill_tree.delete(row)

        total = 0.0
        idx = 0
        for row in self.bill_rows:
            sub = row["qty"] * row["unit_price"]
            total += sub
            self.bill_tree.insert(
                "", "end", iid=f"m{idx}",
                values=(idx + 1, "Medicine", row["name"], row["qty"],
                        f"{row['unit_price']:.2f}", f"{sub:.2f}", "Remove"),
                tags=("medicine",)
            )
            idx += 1

        for row in self.service_rows:
            total += row["price"]
            self.bill_tree.insert(
                "", "end", iid=f"s{idx}",
                values=(idx + 1, "Service", row["service_name"], "—",
                        f"{row['price']:.2f}", f"{row['price']:.2f}", "Remove"),
                tags=("service",)
            )
            idx += 1

        self.total_label.configure(text=f"Grand Total:  Rs. {total:.2f}")

    def _on_bill_click(self, event):
        col = self.bill_tree.identify_column(event.x)
        row_id = self.bill_tree.identify_row(event.y)
        if col != "#7" or not row_id:
            return
        if row_id.startswith("m"):
            med_idx = int(row_id[1:])
            if 0 <= med_idx < len(self.bill_rows):
                self.bill_rows.pop(med_idx)
        elif row_id.startswith("s"):
            svc_abs_idx = int(row_id[1:])
            svc_rel_idx = svc_abs_idx - len(self.bill_rows)
            if 0 <= svc_rel_idx < len(self.service_rows):
                self.service_rows.pop(svc_rel_idx)
        self._refresh_bill_table()

    def _clear_bill(self):
        self.bill_rows.clear()
        self.service_rows.clear()
        self._refresh_bill_table()

    # ─────────────────────────── FINALIZE ────────────────────────────────

    def _finalize_bill(self):
        if not self.selected_patient:
            messagebox.showerror("No Patient", "Please select a patient before generating a bill.")
            return
        if not self.bill_rows and not self.service_rows:
            messagebox.showerror("Empty Bill", "Please add at least one medicine or service.")
            return

        items = []
        for r in self.bill_rows:
            items.append({
                "item_type": "medicine", "item_id": r["medicine_id"],
                "item_name": r["name"], "quantity": r["qty"],
                "unit_price": r["unit_price"], "total_price": r["qty"] * r["unit_price"],
            })
        for r in self.service_rows:
            items.append({
                "item_type": "service", "item_id": r["service_id"],
                "item_name": r["service_name"], "quantity": 1,
                "unit_price": r["price"], "total_price": r["price"],
            })

        try:
            # A billing-only visit (no symptoms/diagnosis) links the bill
            # to this patient's visit history, same as v4 did.
            visit_id = add_visit(self.selected_patient["id"], "", "", "")
            bill_id = create_bill(visit_id, self.selected_patient["id"], items)

            try:
                bill = get_bill_by_id(bill_id)
                bill_items = get_bill_items(bill_id)
                filepath = generate_bill_pdf(bill_id, self.selected_patient, bill, bill_items)
                open_pdf(filepath)
            except Exception as pdf_err:
                messagebox.showwarning(
                    "PDF Warning", f"Bill #{bill_id} saved, but PDF could not be generated:\n\n{pdf_err}")

            self._set_status(f"\u2714  Bill #{bill_id} generated successfully.", error=False)
            self.bill_rows.clear()
            self.service_rows.clear()
            self._refresh_bill_table()
            self.all_medicines = get_all_medicines()
            self.all_services = get_all_services()

        except Exception as e:
            messagebox.showerror("Billing Error", f"Unexpected error:\n\n{e}")
            self._set_status(f"Error: {e}", error=True)

    def _set_status(self, msg, error=False):
        self.status_label.configure(text=msg, text_color="#e74c3c" if error else "#145a32")
