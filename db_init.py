import sqlite3

DB_PATH = "database_v2.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # student_answers table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS student_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        exam_id INTEGER,
        question_no INTEGER,
        selected_option TEXT
    )
    """)

    conn.commit()
    conn.close()