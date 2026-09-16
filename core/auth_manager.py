"""
auth_manager.py — clinic_app_v5 (NEW)

Login system for the clinic app.

  - Passwords are hashed with bcrypt (never stored in plain text).
  - Password reset is done via a security question, chosen at account
    creation — this works fully offline (no email/SMTP server needed,
    which fits a local desktop clinic app). The answer is hashed too.
  - Basic brute-force protection: after `max_login_attempts` wrong
    passwords in a row, the account is locked for `login_lockout_minutes`.

This is a new module — nothing else in the project depended on it before,
so it's safe to add without touching other files (main.py is wired to
call run_login() from ui/login_window.py before opening the main app).
"""

import bcrypt
from datetime import datetime, timedelta

from db.database import get_connection
from config import CONFIG

# Kept in memory for the lifetime of the running app (single-process
# desktop app — no need for a session token or database-backed session).
_CURRENT_USER = None


# ─────────────────────────────────────────────
#  Hashing helpers
# ─────────────────────────────────────────────

def _hash(text: str) -> str:
    return bcrypt.hashpw(text.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check(text: str, hashed: str) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(text.encode("utf-8"), hashed.encode("utf-8"))


def _normalise_answer(answer: str) -> str:
    return answer.strip().lower()


# ─────────────────────────────────────────────
#  Current-user helpers (used by ui/login_window.py and, later,
#  ui/main_window.py to show "Logged in as ...")
# ─────────────────────────────────────────────

def set_current_user(user: dict | None):
    global _CURRENT_USER
    _CURRENT_USER = user


def get_current_user() -> dict | None:
    return _CURRENT_USER


def logout():
    set_current_user(None)


# ─────────────────────────────────────────────
#  Account creation / lookup
# ─────────────────────────────────────────────

def has_any_users() -> bool:
    """True once at least one account exists — used to decide whether to
    show the login form or the first-run 'create admin account' form."""
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return count > 0
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE username=?", (username.strip(),)
        ).fetchone()
    finally:
        conn.close()


def create_user(username: str, full_name: str, password: str,
                security_question: str, security_answer: str,
                role: str = "admin") -> int:
    """
    Raises ValueError if the username is already taken, or if the
    password/security answer look too weak/empty.
    """
    username = username.strip()
    if not username or not password:
        raise ValueError("Username and password are required.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if not security_question.strip() or not security_answer.strip():
        raise ValueError("A security question and answer are required "
                          "so you can reset your password later.")
    if get_user_by_username(username):
        raise ValueError(f"Username '{username}' is already taken.")

    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO users
                   (username, full_name, password_hash, role,
                    security_question, security_answer_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, full_name.strip(), _hash(password), role,
             security_question.strip(), _hash(_normalise_answer(security_answer)))
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  Login (with lockout)
# ─────────────────────────────────────────────

def verify_login(username: str, password: str) -> dict:
    """
    Returns {"ok": True, "user": {...}} on success, or
            {"ok": False, "error": "human readable message"} on failure.
    """
    user = get_user_by_username(username)
    if not user:
        return {"ok": False, "error": "No account with that username."}

    if not user["is_active"]:
        return {"ok": False, "error": "This account has been deactivated."}

    if user["locked_until"]:
        locked_until = datetime.strptime(user["locked_until"], "%Y-%m-%d %H:%M:%S")
        if locked_until > datetime.now():
            minutes_left = max(1, int((locked_until - datetime.now()).total_seconds() // 60) + 1)
            return {"ok": False,
                    "error": f"Too many failed attempts. Try again in {minutes_left} min."}

    if not _check(password, user["password_hash"]):
        _register_failed_attempt(user)
        max_attempts = CONFIG.get("max_login_attempts", 5)
        attempts_left = max(0, max_attempts - (user["failed_attempts"] + 1))
        if attempts_left == 0:
            return {"ok": False,
                    "error": f"Incorrect password. Account locked for "
                             f"{CONFIG.get('login_lockout_minutes', 2)} min."}
        return {"ok": False,
                "error": f"Incorrect password. {attempts_left} attempt(s) left."}

    _register_successful_login(user)
    user_dict = dict(user)
    user_dict.pop("password_hash", None)
    user_dict.pop("security_answer_hash", None)
    set_current_user(user_dict)
    return {"ok": True, "user": user_dict}


def _register_failed_attempt(user):
    conn = get_connection()
    try:
        attempts = user["failed_attempts"] + 1
        max_attempts = CONFIG.get("max_login_attempts", 5)
        if attempts >= max_attempts:
            lockout_minutes = CONFIG.get("login_lockout_minutes", 2)
            locked_until = datetime.now() + timedelta(minutes=lockout_minutes)
            conn.execute(
                "UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?",
                (attempts, locked_until.strftime("%Y-%m-%d %H:%M:%S"), user["id"])
            )
        else:
            conn.execute(
                "UPDATE users SET failed_attempts=? WHERE id=?",
                (attempts, user["id"])
            )
        conn.commit()
    finally:
        conn.close()


def _register_successful_login(user):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE users SET failed_attempts=0, locked_until=NULL,
                                 last_login=NOW() WHERE id=?""",
            (user["id"],)
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  Password reset (security question)
# ─────────────────────────────────────────────

def get_security_question(username: str) -> str | None:
    user = get_user_by_username(username)
    return user["security_question"] if user else None


def reset_password(username: str, security_answer: str, new_password: str) -> dict:
    """
    Returns {"ok": True} on success, {"ok": False, "error": "..."} otherwise.
    """
    if len(new_password) < 6:
        return {"ok": False, "error": "New password must be at least 6 characters."}

    user = get_user_by_username(username)
    if not user:
        return {"ok": False, "error": "No account with that username."}

    if not _check(_normalise_answer(security_answer), user["security_answer_hash"]):
        return {"ok": False, "error": "That answer doesn't match our records."}

    conn = get_connection()
    try:
        conn.execute(
            """UPDATE users SET password_hash=?, failed_attempts=0,
                                 locked_until=NULL WHERE id=?""",
            (_hash(new_password), user["id"])
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def change_password(user_id: int, old_password: str, new_password: str) -> dict:
    """For an in-app 'change my password' screen, once logged in."""
    conn = get_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user or not _check(old_password, user["password_hash"]):
            return {"ok": False, "error": "Current password is incorrect."}
        if len(new_password) < 6:
            return {"ok": False, "error": "New password must be at least 6 characters."}
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (_hash(new_password), user_id)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
