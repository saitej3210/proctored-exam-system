import sqlite3

DB_PATH = "database_v2.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_questions_table():
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE questions ADD COLUMN question_no INTEGER")
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE questions ADD COLUMN correct_option TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()

    print("QUESTIONS TABLE MIGRATED")