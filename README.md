# Clinic App v6

A complete rewrite/upgrade of clinic management app: MySQL instead
of SQLite, a full login system, a redesigned prescription PDF, an
appointment token queue, and every screen (dashboard, patient
registration, billing, medicines, services, search/history,
appointments) wired up and working end to end.

This version merges two things: the v5 upload (which had a
redesigned database layer — cnic/address on patients, symptoms on
visits, unified bill line-items, stock/expiry tracking — but was
missing its `ui/` folder) and v4 (which had the working screens, but on
the older schema). Every screen below has been rebuilt against the new
schema and manager functions, tested against a live MySQL server with
a real GUI, not just written and assumed to work.

---

## What's New in v6

| Area | Before | v6 |
|---|---|---|
| Database | SQLite, single file | **MySQL / MariaDB** — proper server, real foreign keys |
| Login | None | **Full login screen** — animated, first-run account setup, "Forgot password?" flow, lockout after repeated failures |
| Password reset | — | Security-question based (works fully offline, no email server needed) |
| Prescription PDF | Plain text blocks | Logo + colored header badge, patient info bar, **vitals cards (BP / Temperature / Weight)**, highlighted diagnosis box, restyled medicines table, notes box, signature |
| Bill PDF | Plain layout | Reskinned with the same branded header, for a consistent look |
| Vitals | — | Blood Pressure / Temperature / Weight captured per visit, shown on the printed prescription |
| Prescribing | Diagnosis only, no medicines | Full medicine search + dosage/duration/qty right on the visit form |
| Appointments | Backend existed, no screen | **New Appointments screen** — daily token queue, add/start/finish/cancel |
| Patient fields | Name/age/phone/gender/department/doctor | Name/age/phone/gender/**CNIC/address** (department & per-patient doctor dropped — this is a single-doctor clinic) |
| Backups | `sqlite3 .backup()` → `.db` files | `mysqldump` → timestamped `.sql` files |
| Sidebar | Static "v1.0" label | **"Logged in as Dr. X" + Logout**, clinic logo if you add one |

---

## Installation

### 1. Install MySQL

- **Windows:** install [MySQL Community Server](https://dev.mysql.com/downloads/mysql/) (includes the client tools needed for backups)
- **Linux:** `sudo apt install mysql-server mysql-client`
- **macOS:** `brew install mysql`

You don't need to create the database or tables yourself — the app
does that automatically on first run. You just need a MySQL user it
can log in with (`root` with no password works for a single local
install).

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

On some Linux distributions, add `--break-system-packages`.

### 3. Configure the database connection

`clinic_config.json` is created next to `config.py` on first run, with
these defaults — edit them to match your MySQL setup:

```json
"db_host": "localhost",
"db_port": 3306,
"db_user": "root",
"db_password": "",
"db_name": "clinic_app_db"
```

### 4. Run it

```bash
python main.py
```

First launch: backs up (skipped — nothing to back up yet), creates the
database + tables, then shows **"Create your account"** since no user
exists yet. After that, it's a normal sign-in screen.

---

## Login System

- **First run:** shows "Create your account" instead of sign-in. Fill
  in a username, password (6+ characters), and a security
  question/answer — this becomes the admin account.
- **Forgot password?** Enter your username, answer your security
  question, set a new password. Fully offline — no SMTP/email setup
  needed.
- **Lockout:** 5 wrong attempts locks the account for a couple of
  minutes (`max_login_attempts` / `login_lockout_minutes` in
  `clinic_config.json`).
- **Logout:** button at the bottom of the sidebar — returns you to the
  sign-in screen without restarting the app.
- **Disable login entirely** (e.g. while testing): set
  `"login_enabled": false` in `clinic_config.json`.

---

## The Screens

- **Dashboard** — today's visits, queue stats, revenue, low-stock /
  expiring / expired medicine counts, and today's queue table. Quick
  action buttons jump straight to the other screens.
- **New Patient** — patient details (name, age, gender, phone, CNIC,
  address) plus **This Visit** (symptoms, diagnosis, notes) and
  **Vitals** (BP, temperature, weight) and **Prescribe Medicines**
  (searchable, with dosage/duration/quantity). "Save & Print
  Prescription" generates and opens the PDF immediately.
- **Search / History** — search all patients, see their full visit and
  billing history, reprint any past prescription, or jump straight into
  a new visit or a bill for that patient.
- **Appointments** — today's token queue: search a patient and add them
  to the queue, then Start / Mark Done / Cancel each entry. Starting a
  visit from here opens the New Patient screen pre-filled for that
  patient.
- **Billing** — search a patient, add medicines and/or services to a
  bill (with live stock checking), generate and print the bill.
- **Medicines** — inventory with price, stock quantity, unit, and
  expiry date; low-stock/expired rows are colour-flagged.
- **Services** — your price list (consultation fee, X-ray, ultrasound,
  etc.) with descriptions.

---

## Prescription & Bill PDFs

Both share a branded header: your clinic's logo (if you've placed one
— see `assets/README.txt`), clinic name, doctor name, address and
phone, plus a colored badge with the document type, date, and Rx/Bill
number.

The prescription additionally includes a patient info bar, **vitals
cards** (only the ones actually recorded for that visit are shown), a
highlighted **Diagnosis** box, the medicines table, a **Notes** box if
notes were entered, and a signature line.

---

## File Structure

```
clinic_app_v6/
├── main.py                      ← Entry point: backup -> migrate -> login -> main window (loops on Logout)
├── config.py                    ← Settings loader (clinic info + MySQL + login config)
├── clinic_config.json           ← Your clinic name, fees, DB connection, etc. (auto-created)
├── maintenance.py               ← Run monthly
├── requirements.txt
│
├── db/
│   └── database.py              ← MySQL connection, migrations, backup (mysqldump), OPTIMIZE
│
├── core/
│   ├── patient_manager.py
│   ├── visit_manager.py         ← Records symptoms/diagnosis/notes + bp/temperature/weight
│   ├── medicine_manager.py      ← Stock + expiry tracking
│   ├── billing_manager.py       ← Unified medicine+service line items
│   ├── appointment_manager.py   ← Daily token queue
│   ├── service_manager.py
│   └── auth_manager.py          ← Accounts, login, password reset, lockout
│
├── ui/
│   ├── login_window.py          ← Animated login / first-run setup / forgot password
│   ├── main_window.py           ← Sidebar nav, startup alerts, logged-in-as + logout
│   ├── dashboard.py
│   ├── patient_form.py          ← Registration + visit + vitals + prescribing
│   ├── search_screen.py         ← History + reprint
│   ├── appointments_screen.py   ← Token queue
│   ├── billing_screen.py
│   ├── medicine_screen.py
│   └── service_screen.py
│
├── reports/
│   └── pdf_generator.py         ← Prescription + bill PDFs, with logo support
│
├── assets/
│   └── logo.png                 ← Drop your clinic logo here (see assets/README.txt)
│
├── reports_output/               ← PDFs organised by year/month (auto-created)
│
└── backups/                      ← Auto-created, rolling .sql dumps
```

---

## Clinic Configuration

Edit `clinic_config.json`:

```json
{
  "clinic_name": "Al-Shifa Clinic",
  "doctor_name": "Dr. Ahmed",
  "clinic_address": "Main Bazaar, Rahim Yar Khan",
  "clinic_phone": "0300-0000000",
  "default_consultation_fee": 500,
  "low_stock_threshold": 10,
  "expiry_alert_days": 30,
  "max_backups": 30,
  "clinic_logo_path": "assets/logo.png",
  "window_size": "1150x760",
  "db_host": "localhost",
  "db_port": 3306,
  "db_user": "root",
  "db_password": "",
  "db_name": "clinic_app_db",
  "login_enabled": true,
  "max_login_attempts": 5,
  "login_lockout_minutes": 2
}
```

---

## Monthly Maintenance (5 minutes)

```bash
python maintenance.py
```

Checks database health (`CHECK TABLE`), compacts it (`OPTIMIZE TABLE`),
and prints statistics. Run it on the first day of every month.

---

## How to Restore from Backup

**Never edit the live database directly.**

1. Go to the `backups/` folder
2. Find the most recent `clinic_backup_YYYY-MM-DD_HH-MM.sql`
3. Restore it into a **new, empty** database first so you can check it
   before touching production data:
   ```bash
   mysql -u root -p -e "CREATE DATABASE clinic_app_db_test"
   mysql -u root -p clinic_app_db_test < backups/clinic_backup_2026-09-10_08-00.sql
   ```
4. Point `clinic_config.json`'s `db_name` at `clinic_app_db_test`, open
   the app, and verify patients/bills appear correctly
5. Once confirmed, restore the same file into your real database name
   and switch `db_name` back

## Taking a Manual Backup

```python
from db.database import manual_backup
manual_backup("/path/to/usb-drive/clinic_backup.sql")
```

Requires `mysqldump` on your PATH — comes with the MySQL Server/client
install.

---

## How to Move to a New Computer

1. Copy the entire `clinic_app_v6/` folder to the new computer
2. Install MySQL Server there too
3. Export from the old computer: `mysqldump -u root -p clinic_app_db > clinic_export.sql`
4. Install Python + `pip install -r requirements.txt`
5. Import on the new computer:
   ```bash
   mysql -u root -p -e "CREATE DATABASE clinic_app_db"
   mysql -u root -p clinic_app_db < clinic_export.sql
   ```
6. Copy `clinic_config.json` over too, then `python main.py`

---

## Troubleshooting

- **"Unknown database" / connection refused on first run** — make sure
  MySQL Server is running, and `db_host`/`db_port`/`db_user`/
  `db_password` in `clinic_config.json` are correct.
- **Backups silently not happening** — `mysqldump` isn't on your PATH.
  Reinstall MySQL with client tools included, or add its `bin/` folder
  to PATH.
- **Locked out of the app** — wait for the lockout timer shown on
  screen, or reset directly in MySQL:
  ```sql
  UPDATE users SET failed_attempts=0, locked_until=NULL WHERE username='yourname';
  ```
- **Forgot the security answer too** — delete the row and go through
  "Create your account" again (password hashes can't practically be
  reversed):
  ```sql
  DELETE FROM users WHERE username='yourname';
  ```
- **A PDF viewer doesn't open automatically** — the app calls your OS's
  default PDF viewer in the background; the file is still saved in
  `reports_output/YYYY/MM/` even if no viewer is registered — open it
  from there.

---

## Security Notes

- Passwords and security-question answers are hashed with bcrypt —
  never stored in plain text, never logged, never shown on screen
  after entry.
- 5 wrong login attempts locks the account for a few minutes,
  independent of which password was tried — this slows down guessing
  without needing external rate-limiting infrastructure.
- The database connection uses parameterised queries throughout (no
  string-built SQL), so patient-entered text (names, notes, diagnoses)
  can never be interpreted as SQL.
- `clinic_config.json` holds your MySQL credentials in plain text next
  to the app, same as most local desktop database apps — keep the
  clinic PC itself locked down (Windows/user account password) since
  anyone with file access to that folder can read it.

---

## Annual Tasks

- [ ] Run `maintenance.py` and check output
- [ ] Copy the latest `.sql` backup to an external USB drive
- [ ] Check hard drive health (e.g. CrystalDiskInfo on Windows)
- [ ] Confirm a backup restore works on a test database
- [ ] Archive `reports_output/YYYY/` for the past year to an external drive
