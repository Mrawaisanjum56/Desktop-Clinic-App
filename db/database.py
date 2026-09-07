"""
database.py — clinic_app_v5
Improvements over v4:
  - Schema versioning (schema_version table)
  - Proper indexes on all search/filter columns
  - Soft delete (is_deleted flag) on patients, visits, bills
  - SQLite WAL mode for crash safety
  - Safe backup using sqlite3.backup() API
  - Auto-rolling backup (keeps last 30 copies)
  - integrity_check and VACUUM helpers
"""

import sqlite3
import shutil
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "clinic.db"
BACKUP_DIR = Path(__file__).parent.parent / "backups"
CURRENT_SCHEMA_VERSION = 5
MAX_BACKUPS = 30


# ─────────────────────────────────────────────
#  Connection
# ─────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # crash-safe write-ahead log
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL") # safe + faster than FULL
    return conn


# ─────────────────────────────────────────────
#  Initialise / Migrate
# ─────────────────────────────────────────────

def initialise_database():
    """Create tables, indexes, and run any pending migrations."""
    conn = get_connection()
    try:
        _create_schema_version_table(conn)
        current = _get_schema_version(conn)

        if current < 1:
            _migrate_v1(conn)   # baseline tables
        if current < 2:
            _migrate_v2(conn)   # indexes
        if current < 3:
            _migrate_v3(conn)   # soft delete columns
        if current < 4:
            _migrate_v4(conn)   # medicine expiry + stock
        if current < 5:
            _migrate_v5(conn)   # appointment / token queue

        conn.commit()
    finally:
        conn.close()


def _create_schema_version_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER NOT NULL,
            applied_at  TEXT    NOT NULL
        )
    """)


def _get_schema_version(conn) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] if row[0] is not None else 0


def _set_schema_version(conn, version: int):
    conn.execute(
        "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
        (version, datetime.now().isoformat())
    )


# ─────────────────────────────────────────────
#  Migrations
# ─────────────────────────────────────────────

def _migrate_v1(conn):
    """Baseline tables — identical to v4 schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            age         INTEGER,
            gender      TEXT,
            phone       TEXT,
            cnic        TEXT,
            address     TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS visits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id      INTEGER NOT NULL REFERENCES patients(id),
            visit_date      TEXT    DEFAULT (datetime('now')),
            symptoms        TEXT,
            diagnosis       TEXT,
            notes           TEXT
        );

        CREATE TABLE IF NOT EXISTS medicines (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            unit        TEXT,
            price       REAL    DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS prescriptions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_id    INTEGER NOT NULL REFERENCES visits(id),
            medicine_id INTEGER NOT NULL REFERENCES medicines(id),
            dosage      TEXT,
            duration    TEXT,
            quantity    INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS services (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT    NOT NULL,
            price   REAL    DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS bills (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_id        INTEGER NOT NULL REFERENCES visits(id),
            patient_id      INTEGER NOT NULL REFERENCES patients(id),
            total_amount    REAL    DEFAULT 0,
            paid_amount     REAL    DEFAULT 0,
            bill_date       TEXT    DEFAULT (datetime('now')),
            notes           TEXT
        );

        CREATE TABLE IF NOT EXISTS bill_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id     INTEGER NOT NULL REFERENCES bills(id),
            item_type   TEXT    NOT NULL,  -- 'service' or 'medicine'
            item_id     INTEGER,
            item_name   TEXT,
            quantity    INTEGER DEFAULT 1,
            unit_price  REAL    DEFAULT 0,
            total_price REAL    DEFAULT 0
        );
    """)
    _set_schema_version(conn, 1)


def _migrate_v2(conn):
    """Add indexes for all common search and filter queries."""
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_patients_name    ON patients(name);
        CREATE INDEX IF NOT EXISTS idx_patients_phone   ON patients(phone);
        CREATE INDEX IF NOT EXISTS idx_patients_cnic    ON patients(cnic);
        CREATE INDEX IF NOT EXISTS idx_visits_patient   ON visits(patient_id);
        CREATE INDEX IF NOT EXISTS idx_visits_date      ON visits(visit_date);
        CREATE INDEX IF NOT EXISTS idx_bills_patient    ON bills(patient_id);
        CREATE INDEX IF NOT EXISTS idx_bills_date       ON bills(bill_date);
        CREATE INDEX IF NOT EXISTS idx_prescriptions_visit ON prescriptions(visit_id);
    """)
    _set_schema_version(conn, 2)


def _migrate_v3(conn):
    """Add soft-delete columns. Never actually delete patient records."""
    # Use ALTER TABLE … ADD COLUMN — safe on existing databases
    _safe_add_column(conn, "patients", "is_deleted",  "INTEGER DEFAULT 0")
    _safe_add_column(conn, "patients", "deleted_at",  "TEXT")
    _safe_add_column(conn, "visits",   "is_deleted",  "INTEGER DEFAULT 0")
    _safe_add_column(conn, "visits",   "deleted_at",  "TEXT")
    _safe_add_column(conn, "bills",    "is_deleted",  "INTEGER DEFAULT 0")
    _safe_add_column(conn, "bills",    "deleted_at",  "TEXT")

    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_patients_deleted ON patients(is_deleted);
        CREATE INDEX IF NOT EXISTS idx_visits_deleted   ON visits(is_deleted);
        CREATE INDEX IF NOT EXISTS idx_bills_deleted    ON bills(is_deleted);
    """)
    _set_schema_version(conn, 3)


def _migrate_v4(conn):
    """Add stock quantity and expiry date to medicines."""
    _safe_add_column(conn, "medicines", "stock_qty",   "INTEGER DEFAULT 0")
    _safe_add_column(conn, "medicines", "expiry_date", "TEXT")
    _safe_add_column(conn, "medicines", "is_deleted",  "INTEGER DEFAULT 0")
    _set_schema_version(conn, 4)


def _migrate_v5(conn):
    """Add appointment / daily token queue table."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS appointments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  INTEGER NOT NULL REFERENCES patients(id),
            appt_date   TEXT    NOT NULL,
            token_no    INTEGER,
            status      TEXT    DEFAULT 'waiting',  -- waiting/in-progress/done/cancelled
            notes       TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_appt_date   ON appointments(appt_date);
        CREATE INDEX IF NOT EXISTS idx_appt_status ON appointments(status);
    """)
    _set_schema_version(conn, 5)


def _safe_add_column(conn, table: str, column: str, definition: str):
    """ADD COLUMN only if it doesn't already exist — idempotent migration."""
    existing = [
        row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    ]
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# ─────────────────────────────────────────────
#  Soft Delete Helpers
# ─────────────────────────────────────────────

def soft_delete(table: str, record_id: int):
    """Mark a record deleted instead of removing it permanently."""
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE {table} SET is_deleted=1, deleted_at=? WHERE id=?",
            (datetime.now().isoformat(), record_id)
        )
        conn.commit()
    finally:
        conn.close()


def restore_deleted(table: str, record_id: int):
    """Undo a soft delete."""
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE {table} SET is_deleted=0, deleted_at=NULL WHERE id=?",
            (record_id,)
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  Backup
# ─────────────────────────────────────────────

def run_startup_backup():
    """
    Called once on app startup.
    Creates a dated backup using sqlite3's safe backup API,
    then prunes old backups keeping only the last MAX_BACKUPS copies.
    """
    if not DB_PATH.exists():
        return  # nothing to back up yet

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    dest = BACKUP_DIR / f"clinic_backup_{timestamp}.db"

    # sqlite3.backup() is safe even if DB is open — it copies a consistent snapshot
    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(dest)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    _prune_old_backups()


def _prune_old_backups():
    """Delete oldest backups, keeping only the last MAX_BACKUPS files."""
    backups = sorted(BACKUP_DIR.glob("clinic_backup_*.db"))
    while len(backups) > MAX_BACKUPS:
        backups.pop(0).unlink()


def manual_backup(destination: str):
    """Export a backup to a user-chosen path (e.g. USB drive)."""
    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(destination)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()


# ─────────────────────────────────────────────
#  Maintenance
# ─────────────────────────────────────────────

def check_integrity() -> str:
    """Returns 'ok' if database is healthy, otherwise error string."""
    conn = get_connection()
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        return result
    finally:
        conn.close()


def vacuum_database():
    """Compact the database — reclaims space from deleted records."""
    conn = sqlite3.connect(DB_PATH)  # plain connect — VACUUM can't run in WAL tx
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()


def get_db_stats() -> dict:
    """Return useful database statistics for the settings/dashboard screen."""
    conn = get_connection()
    try:
        stats = {}
        stats["size_mb"] = round(DB_PATH.stat().st_size / (1024 * 1024), 2)
        stats["total_patients"] = conn.execute(
            "SELECT COUNT(*) FROM patients WHERE is_deleted=0"
        ).fetchone()[0]
        stats["total_visits"] = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE is_deleted=0"
        ).fetchone()[0]
        stats["total_bills"] = conn.execute(
            "SELECT COUNT(*) FROM bills WHERE is_deleted=0"
        ).fetchone()[0]
        stats["schema_version"] = _get_schema_version(conn)
        backup_files = sorted(BACKUP_DIR.glob("clinic_backup_*.db")) if BACKUP_DIR.exists() else []
        stats["last_backup"] = backup_files[-1].name if backup_files else "No backup yet"
        stats["backup_count"] = len(backup_files)
        return stats
    finally:
        conn.close()
