"""
main.py — clinic_app_v5
Entry point. On startup:
  1. Run database backup (safe sqlite3.backup API)
  2. Initialise / migrate database schema
  3. Check DB integrity
  4. Show alerts (low stock, expiring medicines)
  5. Launch the main window
"""

import sys
from db.database import (
    initialise_database, run_startup_backup,
    check_integrity, get_db_stats
)
from core.medicine_manager import get_low_stock_medicines, get_expiring_medicines
from ui.main_window import MainWindow


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
        # Show error dialog before launching
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

    # ── 4. Collect startup alerts ────────────────────────────────────
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

    # ── 5. Launch UI ─────────────────────────────────────────────────
    app = MainWindow(startup_alerts=alerts)
    app.run()


if __name__ == "__main__":
    main()
