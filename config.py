"""
config.py — clinic_app_v5
All clinic-wide settings in one place.
Edit this file OR expose via the Settings screen in the UI.
"""

import json
from pathlib import Path

_CONFIG_FILE = Path(__file__).parent / "clinic_config.json"

_DEFAULTS = {
    # Clinic identity
    "clinic_name":    "Al-Shifa Clinic",
    "doctor_name":    "Dr. Ahmed",
    "clinic_address": "Main Bazaar, Rahim Yar Khan",
    "clinic_phone":   "0300-0000000",

    # Fees
    "default_consultation_fee": 500,

    # App behaviour
    "app_version":        "6.0",
    "low_stock_threshold": 10,     # alert when medicine qty <= this
    "expiry_alert_days":   30,     # alert N days before expiry
    "max_backups":         30,

    # PDF output folder (relative to project root)
    "reports_output_dir":  "reports_output",

    # Clinic logo (relative to project root) — shown on login screen + prescriptions
    "clinic_logo_path": "assets/logo.png",

    # ── MySQL connection ─────────────────────────────
    # Create the database first (see README), then fill these in.
    "db_host":     "localhost",
    "db_port":     3306,
    "db_user":     "root",
    "db_password": "@Awais.56",
    "db_name":     "clinic_app_db",

    # ── Login / authentication ───────────────────────
    "login_enabled":            True,
    "max_login_attempts":       5,
    "login_lockout_minutes":    2,

    # Window size on launch (ui/main_window.py)
    "window_size": "1150x760",
}


def load() -> dict:
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, "r") as f:
            saved = json.load(f)
        # Merge: saved values override defaults, new defaults fill gaps
        return {**_DEFAULTS, **saved}
    return dict(_DEFAULTS)


def save(settings: dict):
    with open(_CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=2)


# Convenience: load once at import time
CONFIG = load()

# ── Backward-compatible flat constants ───────────────────────
# ui/main_window.py (ported from clinic_app_v4) imports these directly
# rather than reaching into the CONFIG dict. Kept as plain derived
# values (not hardcoded) so editing clinic_config.json still updates
# them everywhere.
APP_TITLE   = f"{CONFIG['clinic_name']} — Management System"
WINDOW_SIZE = CONFIG.get("window_size", "1150x760")
