import sqlite3

# DB file must be SAME as app.py uses
conn = sqlite3.connect("proctored.db")
cur = conn.cursor()

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

print("✅ student_answers table created successfully")