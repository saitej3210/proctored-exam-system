import sqlite3

DB_PATH = "database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def evaluate_exam(student_id, exam_id):
    conn = get_db()
    cur = conn.cursor()

    # -------------------------------------------------
    # 1️⃣ Ensure required tables exist
    # -------------------------------------------------

    # results table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        exam_id INTEGER,
        score INTEGER,
        total INTEGER
    )
    """)

    # questions table (FIX FOR YOUR ERROR)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER,
        question_no INTEGER,
        question TEXT,
        option_a TEXT,
        option_b TEXT,
        option_c TEXT,
        option_d TEXT,
        correct_option TEXT
    )
    """)

    # student_answers table safety
    cur.execute("""
    CREATE TABLE IF NOT EXISTS student_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        exam_id INTEGER,
        question_no INTEGER,
        selected_option TEXT
    )
    """)

    # -------------------------------------------------
    # 2️⃣ Fetch correct answers
    # -------------------------------------------------
    cur.execute("""
        SELECT question_no, correct_option
        FROM questions
        WHERE exam_id = ?
    """, (exam_id,))
    rows = cur.fetchall()

    if not rows:
        print("⚠️ No questions found for exam:", exam_id)
        conn.close()
        return

    correct_answers = {
        row["question_no"]: row["correct_option"] for row in rows
    }

    # -------------------------------------------------
    # 3️⃣ Fetch student answers
    # -------------------------------------------------
    cur.execute("""
        SELECT question_no, selected_option
        FROM student_answers
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))
    student_answers = {
        row["question_no"]: row["selected_option"]
        for row in cur.fetchall()
    }

    # -------------------------------------------------
    # 4️⃣ Evaluate
    # -------------------------------------------------
    score = 0
    for qno, correct in correct_answers.items():
        if student_answers.get(qno) == correct:
            score += 1

    total = len(correct_answers)

    # -------------------------------------------------
    # 5️⃣ Save result
    # -------------------------------------------------
    cur.execute("""
        DELETE FROM results
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))

    cur.execute("""
        INSERT INTO results (student_id, exam_id, score, total)
        VALUES (?, ?, ?, ?)
    """, (student_id, exam_id, score, total))

    conn.commit()
    conn.close()

    print(f"✅ RESULT SAVED: {student_id} | {score}/{total}")