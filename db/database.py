"""
database.py — clinic_app_v6
MySQL edition (replaces the old SQLite layer).

Design goal: every other file in the project (main.py, maintenance.py, and
all of core/*.py) called conn.execute("... ? ...", params) and read results
back with row["column_name"], because that's how sqlite3 works. Rather than
touching every query in every manager file, this module provides a thin
compatibility layer so that surface stays IDENTICAL:

  - get_connection() returns a ConnectionWrapper with the same
    .execute() / .commit() / .close() / .executescript() methods.
  - "?" placeholders are translated to MySQL's "%s" automatically.
  - Rows behave like sqlite3.Row — support row[0] AND row["col"], plus a
    bonus .get("col", default) for safety.
  - DATETIME/DATE/DECIMAL values coming back from the MySQL driver are
    normalised to plain str/float, matching what sqlite3 used to return,
    so existing code like bill_date[:10] or "bill_date LIKE ?" keeps
    working with zero changes.

Other changes from the SQLite version:
  - Proper FOREIGN KEY constraints (InnoDB enforces these natively).
  - Backups now use `mysqldump` (needs MySQL's client tools on PATH)
    instead of sqlite3's backup() API, saved as timestamped .sql files.
  - check_integrity() uses MySQL's CHECK TABLE.
  - vacuum_database() uses MySQL's OPTIMIZE TABLE.
  - get_db_stats() reads database size from INFORMATION_SCHEMA.

Connection settings (host/port/user/password/database name) are read from
clinic_config.json — see config.py. Defaults assume a local MySQL server
with a root user with no password, database name "clinic_app_db".
"""

import subprocess
import shutil
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path

import mysql.connector
from mysql.connector import Error as MySQLError

from config import CONFIG

BACKUP_DIR = Path(__file__).parent.parent / "backups"
CURRENT_SCHEMA_VERSION = 8
MAX_BACKUPS = CONFIG.get("max_backups", 30)

ALL_TABLES = [
    "bill_items", "bills", "prescriptions", "appointments",
    "visits", "medicines", "services", "patients", "users",
    "schema_version",
]


# ─────────────────────────────────────────────
#  Row — mimics sqlite3.Row (index OR key access)
# ─────────────────────────────────────────────

class Row:
    """Behaves like sqlite3.Row: row[0] and row["col"] both work."""
    __slots__ = ("_data", "_keys")

    def __init__(self, columns, values):
        self._keys = columns
        self._data = values

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[key]
        try:
            idx = self._keys.index(key)
        except ValueError:
            raise KeyError(key)
        return self._data[idx]

    def get(self, key, default=None):
        """Bonus over sqlite3.Row — safe lookup with a default."""
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def keys(self):
        return list(self._keys)

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._keys

    def __repr__(self):
        return f"Row({dict(zip(self._keys, self._data))})"


def _normalise(value):
    """Convert MySQL-native types back to what sqlite3 used to hand back."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return float(value)
    return value


# ─────────────────────────────────────────────
#  Cursor / Connection wrappers
# ─────────────────────────────────────────────

class _CursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in self._cursor.description]
        return Row(cols, [_normalise(v) for v in row])

    def fetchall(self):
        rows = self._cursor.fetchall()
        cols = [d[0] for d in self._cursor.description]
        return [Row(cols, [_normalise(v) for v in r]) for r in rows]

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        try:
            self._cursor.close()
        except MySQLError:
            pass


class ConnectionWrapper:
    """
    Wraps a real mysql.connector connection so the rest of the codebase
    can keep calling conn.execute("... ? ...", params) exactly like it
    did with sqlite3. NOTE: the "?" -> "%s" replace is a plain string
    substitution — safe here because none of this project's SQL contains
    a literal "?" character outside of placeholders.
    """

    def __init__(self, raw_conn):
        self._conn = raw_conn
        self._cursors = []

    def execute(self, query, params=()):
        # buffered=True: the whole result set is fetched into client memory
        # immediately, so the connection is never left with an "unread
        # result" pending — which matters here because several places in
        # this project (e.g. vacuum_database's OPTIMIZE TABLE loop) run
        # more than one query in a row on the same connection without
        # necessarily reading each result before moving to the next one.
        cur = self._conn.cursor(buffered=True)
        self._cursors.append(cur)
        cur.execute(query.replace("?", "%s"), params)
        return _CursorWrapper(cur)

    def executescript(self, script: str):
        """Mimics sqlite3's executescript() — runs each ';'-separated
        statement in turn. Fine for this project's DDL (no semicolons
        appear inside string literals in any CREATE TABLE statement)."""
        cur = self._conn.cursor(buffered=True)
        self._cursors.append(cur)
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                cur.execute(statement)

    def commit(self):
        self._conn.commit()

    def close(self):
        for cur in self._cursors:
            try:
                cur.close()
            except MySQLError:
                pass
        self._cursors.clear()
        try:
            self._conn.close()
        except MySQLError:
            pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


# ─────────────────────────────────────────────
#  Connection
# ─────────────────────────────────────────────

def _ensure_database_exists():
    """CREATE DATABASE IF NOT EXISTS — runs once before the first real
    connection, since MySQL errors out if you connect to a database
    that doesn't exist yet."""
    db_name = CONFIG.get("db_name", "clinic_app_db")
    raw = mysql.connector.connect(
        host=CONFIG.get("db_host", "localhost"),
        port=CONFIG.get("db_port", 3306),
        user=CONFIG.get("db_user", "root"),
        password=CONFIG.get("db_password", ""),
    )
    try:
        cur = raw.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
        )
        cur.close()
    finally:
        raw.close()


def get_connection() -> ConnectionWrapper:
    raw = mysql.connector.connect(
        host=CONFIG.get("db_host", "localhost"),
        port=CONFIG.get("db_port", 3306),
        user=CONFIG.get("db_user", "root"),
        password=CONFIG.get("db_password", ""),
        database=CONFIG.get("db_name", "clinic_app_db"),
        autocommit=False,
    )
    return ConnectionWrapper(raw)


# ─────────────────────────────────────────────
#  Initialise / Migrate
# ─────────────────────────────────────────────

def initialise_database():
    """Create the database + tables, and run any pending migrations."""
    _ensure_database_exists()
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
        if current < 6:
            _migrate_v6(conn)   # NEW: users / login accounts
        if current < 7:
            _migrate_v7(conn)   # NEW: visit vitals (BP, temperature, weight)
        if current < 8:
            _migrate_v8(conn)   # NEW: service description + soft delete

        conn.commit()
    finally:
        conn.close()


def _create_schema_version_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INT NOT NULL,
            applied_at  VARCHAR(30) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)


def _get_schema_version(conn) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] if row[0] is not None else 0


def _set_schema_version(conn, version: int):
    conn.execute(
        "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
        (version, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )


# ─────────────────────────────────────────────
#  Migrations
# ─────────────────────────────────────────────

def _migrate_v1(conn):
    """Baseline tables, translated from the SQLite schema to MySQL/InnoDB
    with real FOREIGN KEY constraints."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(150) NOT NULL,
            age         INT,
            gender      VARCHAR(20),
            phone       VARCHAR(30),
            cnic        VARCHAR(30),
            address     TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS visits (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            patient_id      INT NOT NULL,
            visit_date      DATETIME DEFAULT CURRENT_TIMESTAMP,
            symptoms        TEXT,
            diagnosis       TEXT,
            notes           TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS medicines (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(150) NOT NULL,
            unit        VARCHAR(30),
            price       DECIMAL(10,2) DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS prescriptions (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            visit_id    INT NOT NULL,
            medicine_id INT NOT NULL,
            dosage      VARCHAR(100),
            duration    VARCHAR(100),
            quantity    INT DEFAULT 1,
            FOREIGN KEY (visit_id) REFERENCES visits(id),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS services (
            id      INT AUTO_INCREMENT PRIMARY KEY,
            name    VARCHAR(150) NOT NULL,
            price   DECIMAL(10,2) DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS bills (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            visit_id        INT NOT NULL,
            patient_id      INT NOT NULL,
            total_amount    DECIMAL(10,2) DEFAULT 0,
            paid_amount     DECIMAL(10,2) DEFAULT 0,
            bill_date       DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes           TEXT,
            FOREIGN KEY (visit_id) REFERENCES visits(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS bill_items (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            bill_id     INT NOT NULL,
            item_type   VARCHAR(20) NOT NULL,
            item_id     INT,
            item_name   VARCHAR(150),
            quantity    INT DEFAULT 1,
            unit_price  DECIMAL(10,2) DEFAULT 0,
            total_price DECIMAL(10,2) DEFAULT 0,
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    _set_schema_version(conn, 1)


def _migrate_v2(conn):
    """Add indexes for all common search and filter queries.
    Uses a manual existence check instead of 'CREATE INDEX IF NOT EXISTS'
    because that syntax needs MySQL 8.0.29+ / isn't in MariaDB — this
    version works on any MySQL 5.7+/MariaDB install."""
    _safe_create_index(conn, "idx_patients_name",       "patients",      "name")
    _safe_create_index(conn, "idx_patients_phone",      "patients",      "phone")
    _safe_create_index(conn, "idx_patients_cnic",       "patients",      "cnic")
    _safe_create_index(conn, "idx_visits_patient",      "visits",        "patient_id")
    _safe_create_index(conn, "idx_visits_date",         "visits",        "visit_date")
    _safe_create_index(conn, "idx_bills_patient",       "bills",         "patient_id")
    _safe_create_index(conn, "idx_bills_date",          "bills",         "bill_date")
    _safe_create_index(conn, "idx_prescriptions_visit", "prescriptions", "visit_id")
    _set_schema_version(conn, 2)


def _migrate_v3(conn):
    """Add soft-delete columns. Never actually delete patient records."""
    _safe_add_column(conn, "patients", "is_deleted",  "TINYINT(1) DEFAULT 0")
    _safe_add_column(conn, "patients", "deleted_at",  "DATETIME")
    _safe_add_column(conn, "visits",   "is_deleted",  "TINYINT(1) DEFAULT 0")
    _safe_add_column(conn, "visits",   "deleted_at",  "DATETIME")
    _safe_add_column(conn, "bills",    "is_deleted",  "TINYINT(1) DEFAULT 0")
    _safe_add_column(conn, "bills",    "deleted_at",  "DATETIME")

    _safe_create_index(conn, "idx_patients_deleted", "patients", "is_deleted")
    _safe_create_index(conn, "idx_visits_deleted",   "visits",   "is_deleted")
    _safe_create_index(conn, "idx_bills_deleted",    "bills",    "is_deleted")
    _set_schema_version(conn, 3)


def _migrate_v4(conn):
    """Add stock quantity and expiry date to medicines."""
    _safe_add_column(conn, "medicines", "stock_qty",   "INT DEFAULT 0")
    _safe_add_column(conn, "medicines", "expiry_date", "VARCHAR(20)")
    _safe_add_column(conn, "medicines", "is_deleted",  "TINYINT(1) DEFAULT 0")
    _set_schema_version(conn, 4)


def _migrate_v5(conn):
    """Add appointment / daily token queue table."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS appointments (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            patient_id  INT NOT NULL,
            appt_date   DATE NOT NULL,
            token_no    INT,
            status      VARCHAR(20) DEFAULT 'waiting',
            notes       TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    _safe_create_index(conn, "idx_appt_date",   "appointments", "appt_date")
    _safe_create_index(conn, "idx_appt_status", "appointments", "status")
    _set_schema_version(conn, 5)


def _migrate_v6(conn):
    """NEW in v6: user accounts for the login screen."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id                      INT AUTO_INCREMENT PRIMARY KEY,
            username                VARCHAR(50) NOT NULL UNIQUE,
            full_name               VARCHAR(150),
            password_hash           VARCHAR(255) NOT NULL,
            role                    VARCHAR(20) DEFAULT 'admin',
            security_question       VARCHAR(255),
            security_answer_hash    VARCHAR(255),
            failed_attempts         INT DEFAULT 0,
            locked_until            DATETIME,
            is_active               TINYINT(1) DEFAULT 1,
            created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login              DATETIME
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    _set_schema_version(conn, 6)


def _migrate_v7(conn):
    """NEW in v7: vitals captured per visit, printed on the prescription."""
    _safe_add_column(conn, "visits", "bp",          "VARCHAR(20)")
    _safe_add_column(conn, "visits", "temperature", "VARCHAR(20)")
    _safe_add_column(conn, "visits", "weight",       "VARCHAR(20)")
    _set_schema_version(conn, 7)


def _migrate_v8(conn):
    """NEW in v8: services gain a description field (ported from
    clinic_app_v4, which had this) and soft delete, for consistency
    with every other record type in the app."""
    _safe_add_column(conn, "services", "description", "VARCHAR(255) DEFAULT ''")
    _safe_add_column(conn, "services", "is_deleted",  "TINYINT(1) DEFAULT 0")
    _safe_add_column(conn, "services", "deleted_at",  "DATETIME")
    _safe_create_index(conn, "idx_services_deleted", "services", "is_deleted")
    _set_schema_version(conn, 8)


def _safe_add_column(conn, table: str, column: str, definition: str):
    """ADD COLUMN only if it doesn't already exist — idempotent migration."""
    row = conn.execute(
        """SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?""",
        (table, column)
    ).fetchone()
    if not row[0]:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _safe_create_index(conn, index_name: str, table: str, column: str):
    """CREATE INDEX only if it doesn't already exist — idempotent migration."""
    row = conn.execute(
        """SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND INDEX_NAME = ?""",
        (table, index_name)
    ).fetchone()
    if not row[0]:
        conn.execute(f"CREATE INDEX {index_name} ON {table} ({column})")


# ─────────────────────────────────────────────
#  Soft Delete Helpers
# ─────────────────────────────────────────────

def soft_delete(table: str, record_id: int):
    """Mark a record deleted instead of removing it permanently."""
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE {table} SET is_deleted=1, deleted_at=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), record_id)
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
#  Backup  (mysqldump-based)
# ─────────────────────────────────────────────

def run_startup_backup():
    """
    Called once on app startup. Dumps the whole database to a timestamped
    .sql file with mysqldump, then prunes old backups keeping only the
    last MAX_BACKUPS copies. Requires MySQL's client tools (mysqldump) to
    be on PATH — if they aren't, this logs a warning and does nothing,
    exactly like the old code did when a backup failed.
    """
    if shutil.which("mysqldump") is None:
        print("[WARNING] mysqldump not found on PATH — skipping backup. "
              "Install the MySQL client tools to enable automatic backups.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    dest = BACKUP_DIR / f"clinic_backup_{timestamp}.sql"
    _dump_database(dest)
    _prune_old_backups()


def _dump_database(dest_path: Path):
    db_name = CONFIG.get("db_name", "clinic_app_db")
    cmd = [
        "mysqldump",
        f"--host={CONFIG.get('db_host', 'localhost')}",
        f"--port={CONFIG.get('db_port', 3306)}",
        f"--user={CONFIG.get('db_user', 'root')}",
    ]
    password = CONFIG.get("db_password", "")
    if password:
        cmd.append(f"--password={password}")
    cmd.append(db_name)

    with open(dest_path, "w") as f:
        subprocess.run(cmd, stdout=f, check=True)


def manual_backup(destination: str):
    """Export a backup to a user-chosen path (e.g. USB drive)."""
    if shutil.which("mysqldump") is None:
        raise RuntimeError(
            "mysqldump not found on PATH. Install the MySQL client tools first."
        )
    _dump_database(Path(destination))


def _prune_old_backups():
    """Delete oldest backups, keeping only the last MAX_BACKUPS files."""
    backups = sorted(BACKUP_DIR.glob("clinic_backup_*.sql"))
    while len(backups) > MAX_BACKUPS:
        backups.pop(0).unlink()


# ─────────────────────────────────────────────
#  Maintenance
# ─────────────────────────────────────────────

def check_integrity() -> str:
    """Returns 'ok' if every table passes MySQL's CHECK TABLE, otherwise
    a description of what's wrong."""
    conn = get_connection()
    try:
        problems = []
        for table in ALL_TABLES:
            try:
                row = conn.execute(f"CHECK TABLE {table}").fetchone()
                msg = row.get("Msg_text", "") if row else ""
                if str(msg).lower() != "ok":
                    problems.append(f"{table}: {msg}")
            except MySQLError as e:
                problems.append(f"{table}: {e}")
        return "ok" if not problems else "; ".join(problems)
    finally:
        conn.close()


def vacuum_database():
    """Compact the database — MySQL's equivalent of SQLite's VACUUM."""
    conn = get_connection()
    try:
        for table in ALL_TABLES:
            conn.execute(f"OPTIMIZE TABLE {table}")
    finally:
        conn.close()


def get_db_stats() -> dict:
    """Return useful database statistics for the settings/dashboard screen."""
    conn = get_connection()
    try:
        stats = {}
        db_name = CONFIG.get("db_name", "clinic_app_db")

        size_row = conn.execute(
            """SELECT COALESCE(SUM(data_length + index_length), 0)
               FROM INFORMATION_SCHEMA.TABLES WHERE table_schema = ?""",
            (db_name,)
        ).fetchone()
        stats["size_mb"] = round((size_row[0] or 0) / (1024 * 1024), 2)

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

        backup_files = sorted(BACKUP_DIR.glob("clinic_backup_*.sql")) if BACKUP_DIR.exists() else []
        stats["last_backup"] = backup_files[-1].name if backup_files else "No backup yet"
        stats["backup_count"] = len(backup_files)
        return stats
    finally:
        conn.close()
