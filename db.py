import sqlite3
import os
from threading import Lock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database_v2.db")

_db_lock = Lock()

# -----------------------------
# DB CONNECTION
# -----------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------
# INIT DB (RUN ONCE ON START)
# -----------------------------
def init_db():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

        # ---------------- exams ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_name TEXT,
            subject TEXT,
            total_marks INTEGER,
            timer_minutes INTEGER,
            enable_timer INTEGER DEFAULT 0,
            started INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ---------------- students ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            roll TEXT,
            name TEXT,
            status TEXT
        )
        """)

        # ---------------- questions ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            question_no INTEGER,
            question TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct_option TEXT
        )
        """)

        # ---------------- exam_sessions ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id INTEGER,
            status TEXT,
            last_ping TIMESTAMP
        )
        """)

        conn.commit()
        conn.close()