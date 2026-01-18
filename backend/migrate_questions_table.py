from db import get_db

conn = get_db()
cur = conn.cursor()

# 1️⃣ add question_no if missing
try:
    cur.execute("ALTER TABLE questions ADD COLUMN question_no INTEGER")
except Exception:
    pass

# 2️⃣ add correct_option if missing
try:
    cur.execute("ALTER TABLE questions ADD COLUMN correct_option TEXT")
except Exception:
    pass

conn.commit()
conn.close()

print("QUESTIONS TABLE MIGRATED")