"""
maintenance.py — clinic_app_v5
Run this script monthly (or schedule it with Windows Task Scheduler).

Usage:
    python maintenance.py

What it does:
    1. Integrity check
    2. VACUUM (compact database)
    3. Reports folder summary
    4. Old backup pruning reminder
"""

import sys
from pathlib import Path

# Make sure the project root is in the path
sys.path.insert(0, str(Path(__file__).parent))

from db.database import (
    check_integrity, vacuum_database, get_db_stats, BACKUP_DIR, DB_PATH
)
from datetime import datetime


def run():
    print("=" * 55)
    print(f"  Clinic App Maintenance — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    # 1. Integrity check
    print("\n[1/3] Running database integrity check...")
    result = check_integrity()
    if result == "ok":
        print("      ✓ Database is healthy.")
    else:
        print(f"      ✗ PROBLEM FOUND: {result}")
        print("      → Restore from a recent backup in the backups/ folder.")
        sys.exit(1)

    # 2. VACUUM
    print("\n[2/3] Compacting database (VACUUM)...")
    before = DB_PATH.stat().st_size / (1024 * 1024)
    vacuum_database()
    after = DB_PATH.stat().st_size / (1024 * 1024)
    saved = max(0, before - after)
    print(f"      ✓ Done. Size: {after:.2f} MB  (freed: {saved:.2f} MB)")

    # 3. Stats
    print("\n[3/3] Database statistics:")
    stats = get_db_stats()
    print(f"      Patients : {stats['total_patients']}")
    print(f"      Visits   : {stats['total_visits']}")
    print(f"      Bills    : {stats['total_bills']}")
    print(f"      DB size  : {stats['size_mb']} MB")
    print(f"      Schema v : {stats['schema_version']}")
    print(f"      Backups  : {stats['backup_count']} files")
    print(f"      Last bkp : {stats['last_backup']}")

    # 4. PDF folder report
    reports_base = Path(__file__).parent / "reports_output"
    if reports_base.exists():
        pdf_count = len(list(reports_base.rglob("*.pdf")))
        print(f"\n      PDF reports: {pdf_count} files in reports_output/")

    print("\n" + "=" * 55)
    print("  Maintenance complete. No issues found.")
    print("=" * 55)


if __name__ == "__main__":
    run()
