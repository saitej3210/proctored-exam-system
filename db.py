import sqlite3

DB_PATH = "database_v2.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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

    print("QUESTIONS TABLE MIGRATED")