"""
medicine_screen.py — clinic_app_v6

Ported from clinic_app_v4. Field/column renames for the v5/v6 schema:
quantity -> stock_qty, and add_medicine/update_medicine take
(name, unit, price, stock_qty, expiry_date) instead of
(name, price, qty, unit). Added an Expiry Date field, since v5 added
expiry tracking (core.medicine_manager.get_expiring_medicines /
get_expired_medicines) that v4's screen had no way to fill in.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from core.medicine_manager import (
    get_all_medicines, add_medicine, update_medicine, delete_medicine
)


class MedicineScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._editing_id = None
        self._build_ui()
        self._load_medicines()

    def _build_ui(self):
        title_frame = ctk.CTkFrame(self, fg_color="#145a32", corner_radius=10)
        title_frame.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(title_frame, text="Medicine Inventory",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="white").pack(pady=12)

        form = ctk.CTkFrame(self, corner_radius=10)
        form.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(form, text="Add / Edit Medicine",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#145a32").pack(anchor="w", padx=15, pady=(10, 5))

        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0, 12))

        nf = ctk.CTkFrame(row, fg_color="transparent")
        nf.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(nf, text="Medicine Name", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.med_name = ctk.CTkEntry(nf, placeholder_text="e.g. Panadol 500mg", height=36)
        self.med_name.pack(fill="x", pady=(2, 0))

        pf = ctk.CTkFrame(row, fg_color="transparent")
        pf.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(pf, text="Price (Rs.)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.med_price = ctk.CTkEntry(pf, placeholder_text="0.00", height=36, width=90)
        self.med_price.pack(pady=(2, 0))

        qf = ctk.CTkFrame(row, fg_color="transparent")
        qf.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(qf, text="Stock Qty", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.med_qty = ctk.CTkEntry(qf, placeholder_text="0", height=36, width=80)
        self.med_qty.pack(pady=(2, 0))

        uf = ctk.CTkFrame(row, fg_color="transparent")
        uf.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(uf, text="Unit", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.med_unit = ctk.CTkComboBox(
            uf, values=["tablet", "syrup", "injection", "capsule", "sachet", "cream", "drops"],
            width=105, height=36)
        self.med_unit.set("tablet")
        self.med_unit.pack(pady=(2, 0))

        ef = ctk.CTkFrame(row, fg_color="transparent")
        ef.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(ef, text="Expiry Date", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.med_expiry = ctk.CTkEntry(ef, placeholder_text="YYYY-MM-DD", height=36, width=110)
        self.med_expiry.pack(pady=(2, 0))

        bf = ctk.CTkFrame(row, fg_color="transparent")
        bf.pack(side="left")
        ctk.CTkLabel(bf, text=" ", font=ctk.CTkFont(size=11)).pack(anchor="w")
        btn_row = ctk.CTkFrame(bf, fg_color="transparent")
        btn_row.pack(pady=(2, 0))
        self.add_btn = ctk.CTkButton(btn_row, text="Add", width=80, height=36,
                                     fg_color="#145a32", hover_color="#0e3d22",
                                     command=self._add_or_update)
        self.add_btn.pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Clear", width=70, height=36,
                      fg_color="#7f8c8d", hover_color="#5d6d7e",
                      command=self._clear_form).pack(side="left")

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(search_row, text="Search:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 6))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._load_medicines())
        ctk.CTkEntry(search_row, textvariable=self.search_var,
                     placeholder_text="Type medicine name...", height=34, width=250).pack(side="left")
        self.stock_label = ctk.CTkLabel(search_row, text="", font=ctk.CTkFont(size=12),
                                        text_color="#145a32")
        self.stock_label.pack(side="right", padx=10)

        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("ID", "Medicine Name", "Unit", "Price (Rs.)", "Stock", "Expiry", "Action")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=14)
        widths = {"ID": 40, "Medicine Name": 200, "Unit": 75, "Price (Rs.)": 90,
                  "Stock": 65, "Expiry": 100, "Action": 90}
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths[c], anchor="center" if c != "Medicine Name" else "w")

        style = ttk.Style()
        style.configure("Treeview", rowheight=30, font=("Helvetica", 11))
        style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"))
        self.tree.tag_configure("low", background="#fdecea")
        self.tree.tag_configure("ok", background="#eafaf1")
        self.tree.tag_configure("zero", background="#fdedec")
        self.tree.tag_configure("expired", background="#f5c6cb")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8)
        self.tree.bind("<Double-1>", self._on_row_double_click)
        self.tree.bind("<ButtonRelease-1>", self._on_row_click)

        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11))
        self.status_label.pack(pady=(0, 5))

    def _load_medicines(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        query = self.search_var.get().strip()
        meds = get_all_medicines()
        if query:
            meds = [m for m in meds if query.lower() in m["name"].lower()]

        from datetime import date
        today = date.today().isoformat()
        total_items = len(meds)
        low_stock = sum(1 for m in meds if 0 < m["stock_qty"] < 10)
        out_stock = sum(1 for m in meds if m["stock_qty"] == 0)
        label_parts = [f"{total_items} items"]
        if low_stock > 0:
            label_parts.append(f"{low_stock} low stock")
        if out_stock > 0:
            label_parts.append(f"{out_stock} out of stock")
        self.stock_label.configure(
            text="   |   ".join(label_parts),
            text_color="#e74c3c" if (low_stock + out_stock) > 0 else "#145a32"
        )
        for m in meds:
            qty = m["stock_qty"]
            expiry = m.get("expiry_date") or ""
            is_expired = expiry and expiry < today
            tag = "expired" if is_expired else ("zero" if qty == 0 else ("low" if qty < 10 else "ok"))
            self.tree.insert("", "end", iid=str(m["id"]),
                             values=(m["id"], m["name"], m["unit"],
                                     f"{m['price']:.2f}", qty, expiry or "—", "Edit / Del"),
                             tags=(tag,))

    def _on_row_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            if col == "#7":
                row_id = self.tree.identify_row(event.y)
                if row_id:
                    self._show_action_menu(event, int(row_id))

    def _show_action_menu(self, event, med_id):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Edit", command=lambda: self._load_into_form(med_id))
        menu.add_command(label="Delete", command=lambda: self._delete_medicine(med_id))
        menu.tk_popup(event.x_root, event.y_root)

    def _on_row_double_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self._load_into_form(int(row_id))

    def _load_into_form(self, med_id):
        for m in get_all_medicines():
            if m["id"] == med_id:
                self._clear_form()
                self.med_name.insert(0, m["name"])
                self.med_price.insert(0, str(m["price"]))
                self.med_qty.insert(0, str(m["stock_qty"]))
                self.med_unit.set(m["unit"])
                if m.get("expiry_date"):
                    self.med_expiry.insert(0, m["expiry_date"])
                self._editing_id = med_id
                self.add_btn.configure(text="Update", fg_color="#154360")
                break

    def _add_or_update(self):
        name = self.med_name.get().strip()
        price_str = self.med_price.get().strip()
        qty_str = self.med_qty.get().strip()
        unit = self.med_unit.get()
        expiry = self.med_expiry.get().strip()

        if not name:
            messagebox.showerror("Missing Field", "Medicine name is required.")
            self.med_name.focus_set()
            return
        if not price_str:
            messagebox.showerror("Missing Field", "Price is required.")
            self.med_price.focus_set()
            return
        if not qty_str:
            messagebox.showerror("Missing Field", "Stock quantity is required.")
            self.med_qty.focus_set()
            return
        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Price", f"'{price_str}' is not a valid price.\nPlease enter a positive number.")
            self.med_price.focus_set()
            return
        try:
            qty = int(qty_str)
            if qty < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Quantity", f"'{qty_str}' is not a valid quantity.\nPlease enter a whole number (0 or more).")
            self.med_qty.focus_set()
            return

        try:
            if self._editing_id:
                update_medicine(self._editing_id, name, unit, price, qty, expiry)
                self._set_status(f"'{name}' updated.", error=False)
            else:
                add_medicine(name, unit, price, qty, expiry)
                self._set_status(f"'{name}' added to inventory.", error=False)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save medicine:\n\n{e}")
            return

        self._clear_form()
        self._load_medicines()

    def _delete_medicine(self, med_id):
        vals = self.tree.item(str(med_id), "values")
        name = vals[1] if vals else "this medicine"
        if messagebox.askyesno("Confirm Delete", f"Delete '{name}' from inventory?"):
            delete_medicine(med_id)
            self._set_status(f"'{name}' deleted.", error=False)
            self._load_medicines()

    def _clear_form(self):
        self.med_name.delete(0, "end")
        self.med_price.delete(0, "end")
        self.med_qty.delete(0, "end")
        self.med_expiry.delete(0, "end")
        self.med_unit.set("tablet")
        self._editing_id = None
        self.add_btn.configure(text="Add", fg_color="#145a32")

    def _set_status(self, msg, error=False):
        self.status_label.configure(text=msg,
                                    text_color="#e74c3c" if error else "#145a32")
