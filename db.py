import sqlite3
import os
from threading import Lock

# -----------------------------
# DB PATH & LOCK
# -----------------------------
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
# INITIAL TABLE CREATION
# -----------------------------
def init_db():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

        # Exams table
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

        # Questions table
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

        # Students table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            roll TEXT,
            name TEXT,
            status TEXT
        )
        """)

        # Exam sessions table (🔥 THIS WAS MISSING)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id INTEGER,
            last_ping TIMESTAMP,
            status TEXT
        )
        """)

        conn.commit()
        conn.close()

# -----------------------------
# SAFE MIGRATION: QUESTIONS
# -----------------------------
def migrate_questions_table():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(questions)")
        cols = [row[1] for row in cur.fetchall()]

        if "question_no" not in cols:
            cur.execute("ALTER TABLE questions ADD COLUMN question_no INTEGER")

        if "correct_option" not in cols:
            cur.execute("ALTER TABLE questions ADD COLUMN correct_option TEXT")

        conn.commit()
        conn.close()


def init_db():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

        # exams
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

        # questions
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

        # 🔥 ADD THIS (MISSING TABLE)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id INTEGER,
            last_ping INTEGER,
            status TEXT
        )
        """)

        conn.commit()
        conn.close()