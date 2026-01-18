import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database_v2.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
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
        question TEXT,
        option_a TEXT,
        option_b TEXT,
        option_c TEXT,
        option_d TEXT,
        correct_answer TEXT
    )
    """)

    conn.commit()
    conn.close()


def migrate_questions_table():
    conn = get_db()
    cur = conn.cursor()

    cols = [row[1] for row in cur.execute("PRAGMA table_info(questions)")]

    if "question_no" not in cols:
        cur.execute("ALTER TABLE questions ADD COLUMN question_no INTEGER")

    if "correct_option" not in cols:
        cur.execute("ALTER TABLE questions ADD COLUMN correct_option TEXT")

    conn.commit()
    conn.close()