"""
service_manager.py — clinic_app_v6

Ported from clinic_app_v4 (this file wasn't included in the v5 upload).
Rewritten to use the same conn.execute("... ? ...") convention as every
other manager in this project (v4's version called conn.cursor()
directly, which bypasses this project's "?" -> "%s" translation and
Row-wrapping — it would have raised a SQL syntax error against MySQL).
Soft delete added for consistency with patients/visits/bills/medicines.
"""

from db.database import get_connection, soft_delete


def add_service(name: str, price: float, description: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO services (name, price, description)
               VALUES (?, ?, ?)""",
            (name.strip(), price, description.strip())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_all_services(include_deleted: bool = False) -> list:
    conn = get_connection()
    try:
        q = "SELECT * FROM services"
        if not include_deleted:
            q += " WHERE is_deleted=0"
        q += " ORDER BY name"
        return conn.execute(q).fetchall()
    finally:
        conn.close()


def get_service_by_id(service_id: int):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM services WHERE id=?", (service_id,)
        ).fetchone()
    finally:
        conn.close()


def update_service(service_id: int, name: str, price: float, description: str = ""):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE services SET name=?, price=?, description=? WHERE id=?""",
            (name.strip(), price, description.strip(), service_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_service(service_id: int):
    """Soft delete — consistent with the rest of the app (patients,
    visits, bills, medicines never get hard-deleted)."""
    soft_delete("services", service_id)
