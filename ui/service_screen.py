import customtkinter as ctk
from tkinter import ttk, messagebox
from core.service_manager import (
    get_all_services, add_service, update_service, delete_service
)

# Default clinic services pre-loaded on first use
DEFAULT_SERVICES = [
    ("Doctor Consultation Fee", 500.0, "General OPD consultation"),
    ("Ultrasound",              1500.0, "Abdominal / pelvic ultrasound"),
    ("X-Ray",                   800.0, "Plain X-ray (any region)"),
    ("ECG",                     600.0, "Electrocardiogram"),
    ("Blood Test (CBC)",        400.0, "Complete blood count"),
    ("Urine Test",              200.0, "Urine routine examination"),
    ("Dressing / Injection",    150.0, "Wound dressing or injection fee"),
]


class ServiceScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._editing_id = None
        self._seed_defaults()
        self._build_ui()
        self._load_services()

    def _seed_defaults(self):
        """Add default services if the table is empty."""
        existing = get_all_services()
        if not existing:
            for name, price, desc in DEFAULT_SERVICES:
                try:
                    add_service(name, price, desc)
                except Exception:
                    pass

    def _build_ui(self):
        # Title
        title_frame = ctk.CTkFrame(self, fg_color="#c0392b", corner_radius=10)
        title_frame.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(title_frame, text="Clinic Services Manager",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="white").pack(pady=12)

        # Add / Edit form
        form_frame = ctk.CTkFrame(self, corner_radius=10)
        form_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(form_frame, text="Add / Edit Service",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#c0392b").pack(anchor="w", padx=15, pady=(10, 6))

        row = ctk.CTkFrame(form_frame, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0, 6))

        # Service name
        nf = ctk.CTkFrame(row, fg_color="transparent")
        nf.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(nf, text="Service Name *", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.svc_name = ctk.CTkEntry(nf, placeholder_text="e.g. Ultrasound", height=36)
        self.svc_name.pack(fill="x", pady=(2, 0))

        # Price
        pf = ctk.CTkFrame(row, fg_color="transparent")
        pf.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(pf, text="Price (Rs.) *", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.svc_price = ctk.CTkEntry(pf, placeholder_text="500.00", height=36, width=110)
        self.svc_price.pack(pady=(2, 0))

        # Description
        df = ctk.CTkFrame(row, fg_color="transparent")
        df.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(df, text="Description (optional)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.svc_desc = ctk.CTkEntry(df, placeholder_text="Short description", height=36)
        self.svc_desc.pack(fill="x", pady=(2, 0))

        # Buttons
        btn_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(0, 12))

        self.save_btn = ctk.CTkButton(
            btn_row, text="Save Service", width=140, height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#c0392b", hover_color="#922b21",
            command=self._save_service
        )
        self.save_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="Cancel / Clear", width=120, height=38,
            fg_color="#7f8c8d", hover_color="#5d6d7e",
            command=self._clear_form
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(btn_row, text="",
                                          font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left", padx=14)

        # Services table
        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        hdr_row = ctk.CTkFrame(table_frame, fg_color="transparent")
        hdr_row.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(hdr_row, text="All Services",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#c0392b").pack(side="left")
        ctk.CTkButton(hdr_row, text="Refresh", width=80, height=28,
                      fg_color="#566573", hover_color="#2c3e50",
                      font=ctk.CTkFont(size=11),
                      command=self._load_services).pack(side="right")

        cols = ("ID", "Service Name", "Price (Rs.)", "Description", "Edit", "Delete")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        widths = {"ID": 40, "Service Name": 200, "Price (Rs.)": 100,
                  "Description": 260, "Edit": 60, "Delete": 60}
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths[c],
                             anchor="center" if c not in ("Service Name", "Description") else "w")

        style = ttk.Style()
        style.configure("Svc.Treeview", rowheight=30, font=("Helvetica", 11))
        style.configure("Svc.Treeview.Heading", font=("Helvetica", 11, "bold"))
        self.tree.configure(style="Svc.Treeview")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        sb.pack(side="right", fill="y", pady=(0, 8))
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

    def _load_services(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for s in get_all_services():
            self.tree.insert("", "end", iid=str(s["id"]),
                             values=(s["id"], s["name"],
                                     f"Rs. {s['price']:.2f}",
                                     s.get("description", ""),
                                     "✏ Edit", "🗑 Delete"))

    def _on_tree_click(self, event):
        col = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        svc_id = int(row_id)
        if col == "#5":   # Edit
            self._load_for_edit(svc_id)
        elif col == "#6": # Delete
            self._delete_service(svc_id)

    def _load_for_edit(self, svc_id):
        vals = self.tree.item(str(svc_id), "values")
        if not vals:
            return
        self._editing_id = svc_id
        self.svc_name.delete(0, "end")
        self.svc_name.insert(0, vals[1])
        self.svc_price.delete(0, "end")
        # Strip "Rs. " prefix stored in tree display
        raw_price = str(vals[2]).replace("Rs.", "").replace(",", "").strip()
        self.svc_price.insert(0, raw_price)
        self.svc_desc.delete(0, "end")
        self.svc_desc.insert(0, vals[3])
        self.save_btn.configure(text="Update Service", fg_color="#154360")
        self._set_status("Editing service — make changes and click Update.", error=False)

    def _save_service(self):
        name      = self.svc_name.get().strip()
        price_str = self.svc_price.get().strip()
        desc      = self.svc_desc.get().strip()

        if not name:
            messagebox.showerror("Missing Field", "Service name is required.")
            self.svc_name.focus_set()
            return
        if not price_str:
            messagebox.showerror("Missing Field", "Price is required.")
            self.svc_price.focus_set()
            return
        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Price",
                f"'{price_str}' is not a valid price.\nEnter a positive number like 500 or 1500.50.")
            self.svc_price.focus_set()
            return

        try:
            if self._editing_id:
                update_service(self._editing_id, name, price, desc)
                self._set_status(f"'{name}' updated.", error=False)
            else:
                add_service(name, price, desc)
                self._set_status(f"'{name}' added.", error=False)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save service:\n\n{e}")
            return

        self._clear_form()
        self._load_services()

    def _delete_service(self, svc_id):
        vals = self.tree.item(str(svc_id), "values")
        name = vals[1] if vals else "this service"
        if messagebox.askyesno("Confirm Delete",
                               f"Delete '{name}'?\n\nThis cannot be undone."):
            delete_service(svc_id)
            self._set_status(f"'{name}' deleted.", error=False)
            self._load_services()

    def _clear_form(self):
        self.svc_name.delete(0, "end")
        self.svc_price.delete(0, "end")
        self.svc_desc.delete(0, "end")
        self._editing_id = None
        self.save_btn.configure(text="Save Service", fg_color="#c0392b")
        self._set_status("", error=False)

    def _set_status(self, msg, error=False):
        self.status_label.configure(text=msg,
                                     text_color="#e74c3c" if error else "#1a7a4a")
