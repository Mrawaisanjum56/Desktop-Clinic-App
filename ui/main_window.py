"""
main_window.py — clinic_app_v6

Ported from clinic_app_v4 and adapted for v6:
  - Accepts startup_alerts (low stock / expiring medicines) and shows
    them in a dismissible popup shortly after the window opens.
  - Sidebar footer now shows "Logged in as <name>" + a Logout button
    (core.auth_manager.get_current_user() / logout()) instead of the
    old static "v1.0 | Single Machine" label.
  - Dropped the old "Department" / "Attending Doctor" concept — the v5/v6
    schema redesign removed doctor_id/patient_type from patients in favour
    of cnic/address (this is a single-doctor clinic app).
  - Added an "Appointments" nav item for the token-queue feature
    (core/appointment_manager.py) added in v5, which had no screen yet.
"""

import sys
import customtkinter as ctk
from tkinter import messagebox

from ui.patient_form import PatientForm
from ui.billing_screen import BillingScreen
from ui.medicine_screen import MedicineScreen
from ui.search_screen import SearchScreen
from ui.dashboard import DashboardScreen
from ui.service_screen import ServiceScreen
from ui.appointments_screen import AppointmentsScreen
from config import APP_TITLE, WINDOW_SIZE, CONFIG
from core import auth_manager

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

NAV_ITEMS = [
    ("Dashboard",        "#1c2833", "#2c3e50"),
    ("New Patient",      "#1a5276", "#154360"),
    ("Search / History", "#1a5276", "#154360"),
    ("Appointments",     "#b7791f", "#8a5a16"),
    ("Billing",          "#7d3c98", "#5b2c6f"),
    ("Medicines",        "#145a32", "#0e3d22"),
    ("Services",         "#c0392b", "#922b21"),
]


class MainWindow(ctk.CTk):
    def __init__(self, startup_alerts=None):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(1000, 640)
        self._active_nav = None
        self._nav_buttons = {}
        self.logout_requested = False
        self._startup_alerts = startup_alerts or []
        self._build_layout()
        self._navigate("Dashboard")
        if self._startup_alerts:
            self.after(400, self._show_startup_alerts)

    # ─────────────────────────────────────────────
    #  Layout
    # ─────────────────────────────────────────────

    def _build_layout(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0,
                                    fg_color="#1c2833")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Clinic name (+ logo, if one has been placed at clinic_logo_path)
        clinic_header = ctk.CTkFrame(self.sidebar, fg_color="#152535", corner_radius=0)
        clinic_header.pack(fill="x")
        self._build_clinic_header(clinic_header)
        ctk.CTkFrame(clinic_header, height=2, fg_color="#2980b9").pack(fill="x")

        ctk.CTkLabel(self.sidebar, text="NAVIGATION",
                     font=ctk.CTkFont(size=10),
                     text_color="#7f8c8d").pack(pady=(16, 6), padx=14, anchor="w")

        # Nav buttons
        for label, color, hover in NAV_ITEMS:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                height=44,
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
                corner_radius=8,
                fg_color="transparent",
                hover_color="#2c3e50",
                text_color="#bdc3c7",
                command=lambda l=label: self._navigate(l)
            )
            btn.pack(fill="x", padx=10, pady=3)
            self._nav_buttons[label] = btn

        # Bottom: logged-in-as + logout (replaces the old static v1.0 label)
        ctk.CTkFrame(self.sidebar, fg_color="#2c3e50", height=1).pack(
            fill="x", padx=10, pady=(16, 0))

        user = auth_manager.get_current_user()
        user_label = user["full_name"] if user else "Unknown"
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(fill="x", pady=(10, 12), padx=14)
        ctk.CTkLabel(footer, text=f"Logged in as", font=ctk.CTkFont(size=10),
                     text_color="#7f8c8d").pack(anchor="w")
        ctk.CTkLabel(footer, text=user_label, font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#ecf0f1").pack(anchor="w", pady=(0, 6))
        ctk.CTkButton(footer, text="Logout", height=28, font=ctk.CTkFont(size=11),
                      fg_color="#566573", hover_color="#c0392b",
                      command=self._logout).pack(fill="x")
        ctk.CTkLabel(self.sidebar, text=f"v{CONFIG.get('app_version', '6.0')}  |  MySQL",
                     font=ctk.CTkFont(size=9),
                     text_color="#566573").pack(pady=(0, 8))

        # Content area
        self.content_area = ctk.CTkFrame(self, corner_radius=0, fg_color="#f0f3f4")
        self.content_area.pack(side="left", fill="both", expand=True)

        # Status bar
        self.status_bar = ctk.CTkFrame(self.content_area, height=28, corner_radius=0,
                                       fg_color="#dce1e7")
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar.pack_propagate(False)
        self.status_text = ctk.CTkLabel(self.status_bar, text="Ready",
                                        font=ctk.CTkFont(size=11),
                                        text_color="#566573")
        self.status_text.pack(side="left", padx=10, pady=4)

        # Main frame (inside content_area, above status bar)
        self.main_frame = ctk.CTkFrame(self.content_area, corner_radius=0, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True)

        self._current_widget = None

    def _build_clinic_header(self, parent):
        """Clinic name, plus the logo if assets/logo.png (or whatever
        clinic_logo_path points to) exists — falls back to text-only."""
        logo_image = self._load_sidebar_logo()
        if logo_image is not None:
            ctk.CTkLabel(parent, image=logo_image, text="").pack(pady=(16, 4))
        ctk.CTkLabel(parent,
                     text=CONFIG.get("clinic_name", "Clinic"),
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color="white",
                     justify="center", wraplength=170).pack(pady=(0 if logo_image else 18, 4), padx=10)
        doctor_name = CONFIG.get("doctor_name", "")
        if doctor_name:
            ctk.CTkLabel(parent, text=doctor_name, font=ctk.CTkFont(size=11),
                         text_color="#9fb3c8").pack(pady=(0, 14))
        else:
            ctk.CTkFrame(parent, height=6, fg_color="transparent").pack()

    def _load_sidebar_logo(self):
        try:
            from pathlib import Path
            from PIL import Image
            path = Path(__file__).parent.parent / CONFIG.get("clinic_logo_path", "assets/logo.png")
            if not path.exists():
                return None
            img = Image.open(path)
            self._sidebar_logo_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(64, 64))
            return self._sidebar_logo_ref
        except Exception:
            return None

    # ─────────────────────────────────────────────
    #  Startup alerts (low stock / expiring medicines)
    # ─────────────────────────────────────────────

    def _show_startup_alerts(self):
        body = "\n".join(f"•  {a}" for a in self._startup_alerts)
        messagebox.showwarning("Startup Alerts", body)

    # ─────────────────────────────────────────────
    #  Navigation
    # ─────────────────────────────────────────────

    def _navigate(self, label):
        for name, btn in self._nav_buttons.items():
            if name == label:
                btn.configure(fg_color="#2980b9", text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color="#bdc3c7")
        self._active_nav = label
        self._load_screen(label)

    def _clear_main(self):
        if self._current_widget:
            self._current_widget.destroy()
            self._current_widget = None

    def _load_screen(self, label):
        self._clear_main()

        if label == "Dashboard":
            widget = DashboardScreen(self.main_frame, on_navigate=self._navigate)

        elif label == "New Patient":
            widget = PatientForm(self.main_frame, on_patient_saved=self._on_patient_saved)

        elif label == "Search / History":
            widget = SearchScreen(self.main_frame,
                                  on_bill_patient=self._open_billing_for_patient,
                                  on_new_visit=self._open_new_visit_for_patient)

        elif label == "Appointments":
            widget = AppointmentsScreen(self.main_frame,
                                        on_new_visit=self._open_new_visit_for_patient)

        elif label == "Billing":
            widget = BillingScreen(self.main_frame)

        elif label == "Medicines":
            widget = MedicineScreen(self.main_frame)

        elif label == "Services":
            widget = ServiceScreen(self.main_frame)

        else:
            widget = ctk.CTkLabel(self.main_frame, text=label, font=ctk.CTkFont(size=18))

        widget.pack(fill="both", expand=True)
        self._current_widget = widget
        self.status_text.configure(text=f"  {label}")

    def _on_patient_saved(self):
        self.status_text.configure(text="  \u2714  Patient saved successfully")

    def _open_billing_for_patient(self, patient):
        """Called from SearchScreen to jump to Billing with patient prefilled."""
        self._clear_main()
        for name, btn in self._nav_buttons.items():
            btn.configure(fg_color="#2980b9" if name == "Billing" else "transparent",
                          text_color="white" if name == "Billing" else "#bdc3c7")

        widget = BillingScreen(self.main_frame, prefill_patient=patient)
        widget.pack(fill="both", expand=True)
        self._current_widget = widget
        self.status_text.configure(text=f"  Billing — {patient['name']}")

    def _open_new_visit_for_patient(self, patient):
        """Called from SearchScreen/AppointmentsScreen to record a new
        visit (with vitals + prescription) for an existing patient,
        instead of registering them again from scratch."""
        self._clear_main()
        for name, btn in self._nav_buttons.items():
            btn.configure(fg_color="#2980b9" if name == "New Patient" else "transparent",
                          text_color="white" if name == "New Patient" else "#bdc3c7")

        widget = PatientForm(self.main_frame, on_patient_saved=self._on_patient_saved,
                             existing_patient=patient)
        widget.pack(fill="both", expand=True)
        self._current_widget = widget
        self.status_text.configure(text=f"  New Visit — {patient['name']}")

    # ─────────────────────────────────────────────
    #  Logout
    # ─────────────────────────────────────────────

    def _logout(self):
        if messagebox.askyesno("Logout", "Log out and return to the sign-in screen?"):
            auth_manager.logout()
            self.logout_requested = True
            self.destroy()
