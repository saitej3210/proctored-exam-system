import sqlite3
import os
from threading import Lock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database_v2.db")

_db_lock = Lock()

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()

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

        conn.commit()
        conn.close()


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