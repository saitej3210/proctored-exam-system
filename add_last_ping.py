import sqlite3

conn = sqlite3.connect("proctored.db")
cur = conn.cursor()

cur.execute("ALTER TABLE students ADD COLUMN last_ping INTEGER")
cur.execute("ALTER TABLE students ADD COLUMN removed INTEGER DEFAULT 0")

conn.commit()
conn.close()

print("✅ last_ping & removed columns added")