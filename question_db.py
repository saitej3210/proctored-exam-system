import sqlite3

def get_db():
    return sqlite3.connect("proctored.db")

def insert_question(exam_id, qno, question, a, b, c, d):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO questions (exam_id, qno, question, a, b, c, d)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (exam_id, qno, question, a, b, c, d))

    conn.commit()
    conn.close()