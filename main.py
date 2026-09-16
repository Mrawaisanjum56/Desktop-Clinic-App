"""
main.py — clinic_app_v6
Entry point. On startup:
  1. Run database backup (mysqldump)
  2. Initialise / migrate database schema
  3. Check DB integrity
  4. Show the login screen (loops back here after Logout)
  5. Show alerts (low stock, expiring medicines)
  6. Launch the main window
"""

import sys
import os

if getattr(sys, "frozen", False):
    app_dir = sys._MEIPASS
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

from db.database import (
    initialise_database, run_startup_backup,
    check_integrity, get_db_stats
)
from core.medicine_manager import get_low_stock_medicines, get_expiring_medicines
from ui.login_window import run_login
from ui.main_window import MainWindow


def _collect_startup_alerts():
    alerts = []
    low_stock = get_low_stock_medicines()
    if low_stock:
        names = ", ".join(r["name"] for r in low_stock[:5])
        more = f" (+{len(low_stock)-5} more)" if len(low_stock) > 5 else ""
        alerts.append(f"Low stock: {names}{more}")

    expiring = get_expiring_medicines()
    if expiring:
        names = ", ".join(r["name"] for r in expiring[:5])
        more = f" (+{len(expiring)-5} more)" if len(expiring) > 5 else ""
        alerts.append(f"Expiring soon: {names}{more}")
    return alerts


def main():
    # ── 1. Backup before anything else ──────────────────────────────
    try:
        run_startup_backup()
    except Exception as e:
        # Don't block startup if backup fails — just log
        print(f"[WARNING] Backup failed: {e}")

    # ── 2. Init / migrate database ───────────────────────────────────
    initialise_database()

    # ── 3. Integrity check ────────────────────────────────────────────
    integrity = check_integrity()
    if integrity != "ok":
        print(f"[ERROR] Database integrity check failed: {integrity}")
        import customtkinter as ctk
        import tkinter.messagebox as mb
        root = ctk.CTk()
        root.withdraw()
        mb.showerror(
            "Database Error",
            f"Database integrity check failed:\n{integrity}\n\n"
            "Please restore from a backup before continuing."
        )
        sys.exit(1)

    # ── 4-6. Login -> Main window -> (Logout loops back to Login) ────
    while True:
        user = run_login()
        if not user:
            sys.exit(0)   # window closed without signing in

        alerts = _collect_startup_alerts()
        app = MainWindow(startup_alerts=alerts)
        app.mainloop()

        if not getattr(app, "logout_requested", False):
            break   # window closed normally (not via Logout) -> exit app


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import tkinter.messagebox as mb
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        mb.showerror("Startup Error", f"Failed to start application:\n\n{e}")
        root.destroy()
        sys.exit(1)
