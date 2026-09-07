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
    "app_version":        "5.0",
    "low_stock_threshold": 10,     # alert when medicine qty <= this
    "expiry_alert_days":   30,     # alert N days before expiry
    "max_backups":         30,

    # PDF output folder (relative to project root)
    "reports_output_dir":  "reports_output",

    # Login
    "pin_enabled": False,
    "pin_hash":    "",             # bcrypt hash stored here when enabled
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
