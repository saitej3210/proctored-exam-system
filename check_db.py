import sqlite3

conn = sqlite3.connect("exam.db")
cur = conn.cursor()

print("\n--- QUESTIONS TABLE ---")
for row in cur.execute("SELECT * FROM questions"):
    print(row)

print("\n--- OPTIONS TABLE ---")
for row in cur.execute("SELECT * FROM options"):
    print(row)

conn.close()