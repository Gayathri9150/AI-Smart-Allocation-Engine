"""Database helpers for the AI Smart Allocation Engine.

Centralises connection handling and schema creation so the rest of the
app never has to open a raw sqlite3 connection or remember the schema.
"""

import os
import sqlite3
from contextlib import contextmanager

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# DATABASE_PATH lets you point the app at a specific file - this matters
# most on a host like Render, where only a path under a mounted Persistent
# Disk survives redeploys (see README "Deploying to Render"). Locally it
# defaults to a fixed, absolute path next to the project root, so the same
# allocation.db is reused every time you start the app from this folder.
DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.normpath(os.path.join(BASE_DIR, "..", "allocation.db")),
)

# Make sure the folder the db file lives in actually exists (matters when
# DATABASE_PATH points somewhere new, e.g. a freshly mounted disk).
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_db():
    """Yield a sqlite3 connection with row access by column name.

    Commits on a clean exit, rolls back on error, and always closes
    the connection - so callers never have to remember to do it.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist yet, and quietly migrate any
    legacy plaintext passwords left over from an older version of the
    app into hashed ones."""

    print(f"[db] using database at: {DB_PATH}")

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            department TEXT,
            cgpa REAL,
            skills TEXT,
            preferred_location TEXT,
            resume_filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            industry TEXT,
            location TEXT,
            required_skills TEXT,
            minimum_cgpa REAL,
            internship_role TEXT,
            vacancies INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS internships(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            company_name TEXT NOT NULL,
            internship_title TEXT NOT NULL,
            role TEXT NOT NULL,
            required_skills TEXT NOT NULL,
            minimum_cgpa REAL,
            location TEXT,
            vacancies INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        )
        """)

        # --- Lightweight migration for DBs created by the old schema ---
        existing_internship_cols = {
            row["name"] for row in cursor.execute("PRAGMA table_info(internships)")
        }
        if "company_id" not in existing_internship_cols:
            cursor.execute("ALTER TABLE internships ADD COLUMN company_id INTEGER")

        existing_student_cols = {
            row["name"] for row in cursor.execute("PRAGMA table_info(students)")
        }
        if "resume_filename" not in existing_student_cols:
            cursor.execute("ALTER TABLE students ADD COLUMN resume_filename TEXT")

        # Re-hash any passwords stored in plaintext by an earlier version.
        # IMPORTANT: this must recognise every hash method Werkzeug can
        # produce (scrypt is the current default; pbkdf2 and argon2 are
        # older/alternate ones) - otherwise this runs on *every* startup,
        # sees an already-hashed password, assumes it's plaintext, and
        # re-hashes the hash itself - silently breaking every login after
        # the first app restart.
        HASHED_PREFIXES = ("scrypt:", "pbkdf2:", "argon2")
        for table in ("students", "companies"):
            rows = cursor.execute(f"SELECT id, password FROM {table}").fetchall()
            for row in rows:
                if not row["password"].startswith(HASHED_PREFIXES):
                    hashed = generate_password_hash(row["password"])
                    cursor.execute(
                        f"UPDATE {table} SET password = ? WHERE id = ?",
                        (hashed, row["id"]),
                    )
