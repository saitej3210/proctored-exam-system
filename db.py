# db.py
import sqlite3
import os
from threading import Lock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database_v2.db")

_db_lock = Lock()

# -----------------------------
# DB CONNECTION (SINGLE SOURCE)
# -----------------------------
def get_db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------
# INIT DATABASE
# -----------------------------
def init_db():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

        # -------- EXAMS --------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_name TEXT,
            subject TEXT,
            total_marks INTEGER,
            timer_minutes INTEGER,
            enable_timer INTEGER DEFAULT 0,
            started INTEGER DEFAULT 0,
            results_released INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # -------- STUDENTS --------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            roll TEXT,
            name TEXT,
            status TEXT,
            removed INTEGER DEFAULT 0
        )
        """)

        # -------- QUESTIONS --------
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

        # -------- STUDENT ANSWERS ✅ FIX --------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS student_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            exam_id INTEGER,
            question_no INTEGER,
            selected_option TEXT
        )
        """)

        # -------- EXAM SESSIONS --------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id INTEGER,
            status TEXT,
            last_ping TIMESTAMP,
            total_paused_seconds INTEGER DEFAULT 0,
            paused_at TIMESTAMP
        )
        """)

        # -------- RESULTS (FINAL & CORRECT) --------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id INTEGER,
            correct INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
        conn.close()

def migrate_exam_violations_table():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            exam_id INTEGER,
            event_type TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()      