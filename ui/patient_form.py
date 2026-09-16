"""
patient_form.py — clinic_app_v6

Rebuilt from clinic_app_v4's PatientForm. Major changes:
  - Patient fields updated for the v5/v6 schema: dropped Department /
    Attending Doctor (that concept doesn't exist anymore — single-doctor
    clinic), added CNIC and Address (new in v5).
  - The visit section now has real Symptoms / Diagnosis / Notes fields
    plus Blood Pressure / Temperature / Weight vitals — this is the
    "prettier prescription" ask: these are exactly the fields that show
    up as vitals cards + diagnosis box on the printed prescription PDF.
  - Added a "Prescribe Medicines" section (searchable, with dosage /
    duration / quantity) — v4 had no way to actually attach medicines to
    a visit from this screen at all.
  - Works in two modes: registering a brand new patient, or (when opened
    via existing_patient=) recording a new visit for a patient who
    already exists, without re-entering their details.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

from core.patient_manager import add_patient
from core.visit_manager import add_visit, save_prescriptions, get_visit_by_id
from core.medicine_manager import get_all_medicines
from reports.pdf_generator import generate_prescription_pdf, open_pdf


class PatientForm(ctk.CTkFrame):
    def __init__(self, master, on_patient_saved=None, existing_patient=None):
        super().__init__(master, fg_color="transparent")
        self.on_patient_saved = on_patient_saved
        self.existing_patient = existing_patient
        self.selected_gender = ctk.StringVar(value="Male")
        self.all_medicines = get_all_medicines()
        self.rx_rows = []              # [{medicine_id, name, unit, dosage, duration, qty}]
        self._selected_medicine = None
        self._med_listbox = None
        self._build_ui()

    # ─────────────────────────────────────────────
    #  UI
    # ─────────────────────────────────────────────

    def _build_ui(self):
        is_existing = self.existing_patient is not None
        title = f"New Visit — {self.existing_patient['name']}" if is_existing else "New Patient Registration"

        title_frame = ctk.CTkFrame(self, fg_color="#1a5276", corner_radius=10)
        title_frame.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(title_frame, text=title,
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="white").pack(pady=12)

        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=10, pady=10)

        if is_existing:
            self._build_existing_patient_banner(content)
        else:
            self._build_patient_fields(content)

        self._build_visit_fields(content)
        self._build_vitals_fields(content)
        self._build_prescribe_section(content)

        action_frame = ctk.CTkFrame(content, fg_color="transparent")
        action_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            action_frame, text="Save & Print Prescription",
            height=50, font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#1a5276", hover_color="#154360",
            command=self._save_and_print
        ).pack(side="left", expand=True, fill="x", padx=(0, 8))

        ctk.CTkButton(
            action_frame, text="Save Only",
            height=50, width=130,
            font=ctk.CTkFont(size=14),
            fg_color="#2e4057", hover_color="#1e2d3d",
            command=self._save_only
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(content, text="", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=4)

    def _build_existing_patient_banner(self, content):
        banner = ctk.CTkFrame(content, corner_radius=10, fg_color="#eaf4fb")
        banner.pack(fill="x", pady=(0, 12))
        p = self.existing_patient
        ctk.CTkLabel(
            banner,
            text=f"{p['name']}   |   Age: {p.get('age','—')}   |   {p.get('gender','—')}"
                 f"   |   {p.get('phone','—')}   |   Patient ID: {p['id']}",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#1a5276"
        ).pack(anchor="w", padx=15, pady=12)

    def _build_patient_fields(self, content):
        fields_frame = ctk.CTkFrame(content, corner_radius=10)
        fields_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(fields_frame, text="Patient Information",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#1a5276").pack(anchor="w", padx=15, pady=(10, 5))

        row1 = ctk.CTkFrame(fields_frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=(0, 8))

        name_frame = ctk.CTkFrame(row1, fg_color="transparent")
        name_frame.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(name_frame, text="Full Name *", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(name_frame, placeholder_text="Patient full name",
                                       height=38, font=ctk.CTkFont(size=13))
        self.name_entry.pack(fill="x", pady=(2, 0))

        age_frame = ctk.CTkFrame(row1, fg_color="transparent")
        age_frame.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(age_frame, text="Age *", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.age_entry = ctk.CTkEntry(age_frame, placeholder_text="Age",
                                      height=38, width=90, font=ctk.CTkFont(size=13))
        self.age_entry.pack(pady=(2, 0))

        phone_frame = ctk.CTkFrame(row1, fg_color="transparent")
        phone_frame.pack(side="left")
        ctk.CTkLabel(phone_frame, text="Phone *", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.phone_entry = ctk.CTkEntry(phone_frame, placeholder_text="03xx-xxxxxxx",
                                        height=38, width=155, font=ctk.CTkFont(size=13))
        self.phone_entry.pack(pady=(2, 0))

        row2 = ctk.CTkFrame(fields_frame, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=(0, 8))

        cnic_frame = ctk.CTkFrame(row2, fg_color="transparent")
        cnic_frame.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(cnic_frame, text="CNIC", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.cnic_entry = ctk.CTkEntry(cnic_frame, placeholder_text="xxxxx-xxxxxxx-x",
                                       height=38, width=180, font=ctk.CTkFont(size=13))
        self.cnic_entry.pack(pady=(2, 0))

        addr_frame = ctk.CTkFrame(row2, fg_color="transparent")
        addr_frame.pack(side="left", expand=True, fill="x")
        ctk.CTkLabel(addr_frame, text="Address", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.address_entry = ctk.CTkEntry(addr_frame, placeholder_text="City / area",
                                          height=38, font=ctk.CTkFont(size=13))
        self.address_entry.pack(fill="x", pady=(2, 0))

        ctk.CTkFrame(fields_frame, height=1, fg_color="#dddddd").pack(fill="x", padx=15, pady=8)

        gender_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
        gender_frame.pack(fill="x", padx=15, pady=(0, 12))
        ctk.CTkLabel(gender_frame, text="Gender",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 6))
        gender_btn_frame = ctk.CTkFrame(gender_frame, fg_color="transparent")
        gender_btn_frame.pack(anchor="w")
        self.gender_btns = {}
        for g in ["Male", "Female"]:
            btn = ctk.CTkButton(
                gender_btn_frame, text=g, width=130, height=44,
                font=ctk.CTkFont(size=14, weight="bold"),
                fg_color="#2980b9" if g == "Male" else "#7f8c8d",
                hover_color="#1a6fa0",
                command=lambda x=g: self._select_gender(x)
            )
            btn.pack(side="left", padx=(0, 10))
            self.gender_btns[g] = btn

    def _build_visit_fields(self, content):
        visit_frame = ctk.CTkFrame(content, corner_radius=10)
        visit_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(visit_frame, text="This Visit",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#1a5276").pack(anchor="w", padx=15, pady=(10, 5))

        row = ctk.CTkFrame(visit_frame, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0, 4))

        sf = ctk.CTkFrame(row, fg_color="transparent")
        sf.pack(side="left", expand=True, fill="both", padx=(0, 6))
        ctk.CTkLabel(sf, text="Symptoms", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.symptoms_entry = ctk.CTkTextbox(sf, height=70, font=ctk.CTkFont(size=13))
        self.symptoms_entry.pack(fill="both", pady=(2, 0))

        df = ctk.CTkFrame(row, fg_color="transparent")
        df.pack(side="left", expand=True, fill="both", padx=(6, 0))
        ctk.CTkLabel(df, text="Diagnosis", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.diagnosis_entry = ctk.CTkTextbox(df, height=70, font=ctk.CTkFont(size=13))
        self.diagnosis_entry.pack(fill="both", pady=(2, 0))

        nf = ctk.CTkFrame(visit_frame, fg_color="transparent")
        nf.pack(fill="x", padx=15, pady=(8, 12))
        ctk.CTkLabel(nf, text="Notes (advice, follow-up, etc.)", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.notes_entry = ctk.CTkTextbox(nf, height=60, font=ctk.CTkFont(size=13))
        self.notes_entry.pack(fill="x", pady=(2, 0))

    def _build_vitals_fields(self, content):
        vitals_frame = ctk.CTkFrame(content, corner_radius=10)
        vitals_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(vitals_frame, text="Vitals (shown on the printed prescription)",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#0f8b8d").pack(anchor="w", padx=15, pady=(10, 5))

        row = ctk.CTkFrame(vitals_frame, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0, 12))

        bpf = ctk.CTkFrame(row, fg_color="transparent")
        bpf.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(bpf, text="Blood Pressure", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.bp_entry = ctk.CTkEntry(bpf, placeholder_text="e.g. 120/80", height=38)
        self.bp_entry.pack(fill="x", pady=(2, 0))

        tf = ctk.CTkFrame(row, fg_color="transparent")
        tf.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(tf, text="Temperature", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.temp_entry = ctk.CTkEntry(tf, placeholder_text="e.g. 98.6°F", height=38)
        self.temp_entry.pack(fill="x", pady=(2, 0))

        wf = ctk.CTkFrame(row, fg_color="transparent")
        wf.pack(side="left", expand=True, fill="x")
        ctk.CTkLabel(wf, text="Weight", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.weight_entry = ctk.CTkEntry(wf, placeholder_text="e.g. 70kg", height=38)
        self.weight_entry.pack(fill="x", pady=(2, 0))

    def _build_prescribe_section(self, content):
        rx_frame = ctk.CTkFrame(content, corner_radius=10)
        rx_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(rx_frame, text="Prescribe Medicines",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#1a5276").pack(anchor="w", padx=15, pady=(10, 5))

        row = ctk.CTkFrame(rx_frame, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0, 4))

        mf = ctk.CTkFrame(row, fg_color="transparent")
        mf.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(mf, text="Medicine", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.med_search_entry = ctk.CTkEntry(mf, placeholder_text="Type to search medicine...", height=36)
        self.med_search_entry.pack(fill="x", pady=(2, 0))
        self.med_search_entry.bind("<KeyRelease>", self._filter_medicines)

        df = ctk.CTkFrame(row, fg_color="transparent")
        df.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(df, text="Dosage", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.dosage_entry = ctk.CTkEntry(df, placeholder_text="1 tablet", height=36, width=120)
        self.dosage_entry.pack(pady=(2, 0))

        durf = ctk.CTkFrame(row, fg_color="transparent")
        durf.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(durf, text="Duration", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.duration_entry = ctk.CTkEntry(durf, placeholder_text="5 days", height=36, width=110)
        self.duration_entry.pack(pady=(2, 0))

        qf = ctk.CTkFrame(row, fg_color="transparent")
        qf.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(qf, text="Qty", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.rx_qty_entry = ctk.CTkEntry(qf, placeholder_text="1", height=36, width=60)
        self.rx_qty_entry.pack(pady=(2, 0))

        ctk.CTkButton(
            row, text="+ Add", width=80, height=36,
            fg_color="#1a5276", hover_color="#154360",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._add_medicine_to_rx
        ).pack(side="left", pady=(16, 0))

        self.med_listbox_frame = ctk.CTkFrame(rx_frame, fg_color="transparent")
        self.med_listbox_frame.pack(fill="x", padx=15, pady=(2, 6))

        table_wrap = ctk.CTkFrame(rx_frame, fg_color="transparent")
        table_wrap.pack(fill="x", padx=15, pady=(0, 12))
        cols = ("#", "Medicine", "Dosage", "Duration", "Qty", "Remove")
        self.rx_tree = ttk.Treeview(table_wrap, columns=cols, show="headings", height=5)
        widths = {"#": 30, "Medicine": 220, "Dosage": 130, "Duration": 100, "Qty": 50, "Remove": 70}
        for c in cols:
            self.rx_tree.heading(c, text=c)
            self.rx_tree.column(c, width=widths[c], anchor="w" if c == "Medicine" else "center")
        self.rx_tree.pack(fill="x")
        self.rx_tree.bind("<ButtonRelease-1>", self._on_rx_click)

    # ─────────────────────────────────────────────
    #  Gender selection
    # ─────────────────────────────────────────────

    def _select_gender(self, gender):
        self.selected_gender.set(gender)
        color_map = {"Male": "#2980b9", "Female": "#c0392b"}
        for g, btn in self.gender_btns.items():
            btn.configure(fg_color=color_map[g] if g == gender else "#7f8c8d")

    # ─────────────────────────────────────────────
    #  Medicine search / prescribe list
    # ─────────────────────────────────────────────

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
            selectbackground="#d2e4f0", activestyle="none"
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

    def _add_medicine_to_rx(self):
        if not self._selected_medicine:
            self._set_status("Select a medicine first.", error=True)
            return
        qty_str = self.rx_qty_entry.get().strip() or "1"
        try:
            qty = int(qty_str)
            if qty <= 0:
                raise ValueError
        except ValueError:
            self._set_status("Quantity must be a positive whole number.", error=True)
            return

        med = self._selected_medicine
        self.rx_rows.append({
            "medicine_id": med["id"],
            "name": med["name"],
            "dosage": self.dosage_entry.get().strip(),
            "duration": self.duration_entry.get().strip(),
            "quantity": qty,
        })
        self._refresh_rx_table()
        self._selected_medicine = None
        self.med_search_entry.delete(0, "end")
        self.dosage_entry.delete(0, "end")
        self.duration_entry.delete(0, "end")
        self.rx_qty_entry.delete(0, "end")
        self._set_status("", error=False)

    def _refresh_rx_table(self):
        for row in self.rx_tree.get_children():
            self.rx_tree.delete(row)
        for i, r in enumerate(self.rx_rows):
            self.rx_tree.insert("", "end", iid=str(i), values=(
                i + 1, r["name"], r["dosage"] or "—", r["duration"] or "—",
                r["quantity"], "✕ Remove"
            ))

    def _on_rx_click(self, event):
        col = self.rx_tree.identify_column(event.x)
        row_id = self.rx_tree.identify_row(event.y)
        if col == "#6" and row_id:
            idx = int(row_id)
            if 0 <= idx < len(self.rx_rows):
                self.rx_rows.pop(idx)
                self._refresh_rx_table()

    # ─────────────────────────────────────────────
    #  Validation
    # ─────────────────────────────────────────────

    def _validate(self):
        if self.existing_patient is not None:
            return True

        name = self.name_entry.get().strip()
        age_str = self.age_entry.get().strip()
        phone = self.phone_entry.get().strip()

        if not name:
            messagebox.showerror("Missing Field", "Patient name is required.\n\nPlease enter the full name.")
            self.name_entry.focus_set()
            return None
        if not age_str:
            messagebox.showerror("Missing Field", "Age is required.\n\nPlease enter a valid age.")
            self.age_entry.focus_set()
            return None
        if not age_str.isdigit() or not (0 < int(age_str) < 150):
            messagebox.showerror("Invalid Age", f"'{age_str}' is not a valid age.\n\nPlease enter a number between 1 and 149.")
            self.age_entry.focus_set()
            return None
        if not phone:
            messagebox.showerror("Missing Field", "Phone number is required.\n\nPlease enter a contact number.")
            self.phone_entry.focus_set()
            return None

        return True

    # ─────────────────────────────────────────────
    #  Save
    # ─────────────────────────────────────────────

    def _resolve_patient_id(self):
        """Returns (patient_id, patient_dict) — creates a new patient
        unless we were opened for an existing one."""
        if self.existing_patient is not None:
            return self.existing_patient["id"], self.existing_patient

        name = self.name_entry.get().strip()
        age = int(self.age_entry.get().strip())
        phone = self.phone_entry.get().strip()
        cnic = self.cnic_entry.get().strip()
        address = self.address_entry.get().strip()
        gender = self.selected_gender.get()

        patient_id = add_patient(name, age, gender, phone, cnic, address)
        patient = {"id": patient_id, "name": name, "age": age,
                  "gender": gender, "phone": phone, "cnic": cnic, "address": address}
        return patient_id, patient

    def _save_visit(self):
        patient_id, patient = self._resolve_patient_id()

        symptoms = self.symptoms_entry.get("1.0", "end").strip()
        diagnosis = self.diagnosis_entry.get("1.0", "end").strip()
        notes = self.notes_entry.get("1.0", "end").strip()
        bp = self.bp_entry.get().strip()
        temperature = self.temp_entry.get().strip()
        weight = self.weight_entry.get().strip()

        visit_id = add_visit(patient_id, symptoms, diagnosis, notes,
                             bp=bp, temperature=temperature, weight=weight)

        if self.rx_rows:
            save_prescriptions(visit_id, [
                {"medicine_id": r["medicine_id"], "dosage": r["dosage"],
                 "duration": r["duration"], "quantity": r["quantity"]}
                for r in self.rx_rows
            ])

        visit = get_visit_by_id(visit_id)
        prescriptions = [
            {"medicine_name": r["name"], "dosage": r["dosage"],
             "duration": r["duration"], "quantity": r["quantity"]}
            for r in self.rx_rows
        ]
        return patient_id, patient, visit_id, visit, prescriptions

    def _save_only(self):
        if not self._validate():
            return
        try:
            patient_id, patient, visit_id, visit, prescriptions = self._save_visit()
            self._set_status(f"\u2714  Saved successfully. Patient ID: {patient_id}", error=False)
            self._reset()
            if self.on_patient_saved:
                self.on_patient_saved()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save:\n\n{e}")
            self._set_status("Save failed — see error dialog.", error=True)

    def _save_and_print(self):
        if not self._validate():
            return
        try:
            patient_id, patient, visit_id, visit, prescriptions = self._save_visit()
            try:
                filepath = generate_prescription_pdf(visit_id, patient, visit, prescriptions)
                open_pdf(filepath)
            except Exception as pdf_err:
                messagebox.showwarning("PDF Warning",
                    f"Saved (Patient ID: {patient_id}), but the prescription PDF "
                    f"could not be generated:\n\n{pdf_err}")
            self._set_status(f"\u2714  Saved & prescription printed. Patient ID: {patient_id}", error=False)
            self._reset()
            if self.on_patient_saved:
                self.on_patient_saved()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save:\n\n{e}")
            self._set_status("Save failed — see error dialog.", error=True)

    def _set_status(self, msg, error=False):
        self.status_label.configure(text=msg, text_color="#e74c3c" if error else "#1a7a4a")

    def _reset(self):
        if self.existing_patient is None:
            self.name_entry.delete(0, "end")
            self.age_entry.delete(0, "end")
            self.phone_entry.delete(0, "end")
            self.cnic_entry.delete(0, "end")
            self.address_entry.delete(0, "end")
            self._select_gender("Male")
        self.symptoms_entry.delete("1.0", "end")
        self.diagnosis_entry.delete("1.0", "end")
        self.notes_entry.delete("1.0", "end")
        self.bp_entry.delete(0, "end")
        self.temp_entry.delete(0, "end")
        self.weight_entry.delete(0, "end")
        self.rx_rows.clear()
        self._refresh_rx_table()
        self.all_medicines = get_all_medicines()
