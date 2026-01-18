import sqlite3
import os
from threading import Lock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "proctored.db")

_db_lock = Lock()

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- INIT ----------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            roll TEXT,
            name TEXT,
            status TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            question_no INTEGER,
            question_text TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS answer_key (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            question_no INTEGER,
            correct_option TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            roll TEXT,
            question_id INTEGER,
            selected_option TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HELPERS ----------------
def insert_student(exam_id, roll, name, status):
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO students (exam_id, roll, name, status)
            VALUES (?, ?, ?, ?)
        """, (exam_id, roll, name, status))
        conn.commit()
        conn.close()

def insert_question(exam_id, qno, text, a, b, c, d):
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO questions
            (exam_id, question_no, question_text, option_a, option_b, option_c, option_d)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (exam_id, qno, text, a, b, c, d))
        conn.commit()
        conn.close()

def insert_answer_key(exam_id, qno, correct):
    with _db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO answer_key (exam_id, question_no, correct_option)
            VALUES (?, ?, ?)
        """, (exam_id, qno, correct))
        conn.commit()
        conn.close()