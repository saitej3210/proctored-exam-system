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
# INIT DB (CREATE TABLES)
# -----------------------------
def init_db():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

        # ---------------- EXAMS ----------------
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

        # ---------------- STUDENTS ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            roll TEXT,
            name TEXT,
            status TEXT
        )
        """)

        # ---------------- QUESTIONS ----------------
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

        # ---------------- EXAM SESSIONS ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id INTEGER,
            status TEXT,
            last_ping TIMESTAMP,
            timer_enabled INTEGER DEFAULT 0,
            timer_minutes INTEGER DEFAULT 0,
            timer_started_at TIMESTAMP
        )
        """)

        # ---------------- RESULTS ---------------- ✅ NEW
        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id INTEGER,
            score INTEGER,
            total_questions INTEGER,
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
        conn.close()


# -----------------------------
# MIGRATIONS (SAFE)
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


def migrate_students_table():
    # students table already stable – kept for future safety
    pass


def migrate_exam_sessions_table():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(exam_sessions)")
        cols = [row[1] for row in cur.fetchall()]

        if "timer_enabled" not in cols:
            cur.execute("ALTER TABLE exam_sessions ADD COLUMN timer_enabled INTEGER DEFAULT 0")

        if "timer_minutes" not in cols:
            cur.execute("ALTER TABLE exam_sessions ADD COLUMN timer_minutes INTEGER DEFAULT 0")

        if "timer_started_at" not in cols:
            cur.execute("ALTER TABLE exam_sessions ADD COLUMN timer_started_at TIMESTAMP")

        conn.commit()
        conn.close()


def migrate_results_table():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id INTEGER,
            correct INTEGER,
            total INTEGER,
            total_questions INTEGER,
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("PRAGMA table_info(results)")
        cols = [row[1] for row in cur.fetchall()]

        if "correct" not in cols:
            cur.execute("ALTER TABLE results ADD COLUMN correct INTEGER DEFAULT 0")

        if "total" not in cols:
            cur.execute("ALTER TABLE results ADD COLUMN total INTEGER DEFAULT 0")

        if "total_questions" not in cols:
            cur.execute("ALTER TABLE results ADD COLUMN total_questions INTEGER DEFAULT 0")

        if "evaluated_at" not in cols:
            cur.execute("ALTER TABLE results ADD COLUMN evaluated_at TIMESTAMP")

        conn.commit()
        conn.close()

def migrate_exams_table():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(exams)")
        cols = [row[1] for row in cur.fetchall()]

        if "results_released" not in cols:
            cur.execute(
                "ALTER TABLE exams ADD COLUMN results_released INTEGER DEFAULT 0"
            )

        conn.commit()
        conn.close()