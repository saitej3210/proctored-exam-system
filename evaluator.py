from db import get_db

def evaluate_exam(student_roll, exam_id):
    conn = get_db()
    cur = conn.cursor()

    # ----------------------------
    # Fetch correct vs selected
    # ----------------------------
    cur.execute("""
        SELECT
            q.question_no,
            q.correct_option,
            sa.selected_option
        FROM questions q
        LEFT JOIN student_answers sa
            ON q.question_no = sa.question_no
            AND sa.student_id = ?
            AND sa.exam_id = ?
        WHERE q.exam_id = ?
        ORDER BY q.question_no
    """, (student_roll, exam_id, exam_id))

    rows = cur.fetchall()

    correct = 0
    total = len(rows)

    for r in rows:
        if r["selected_option"] == r["correct_option"]:
            correct += 1

    # ----------------------------
    # DELETE OLD RESULT (VERY IMPORTANT)
    # ----------------------------
    cur.execute("""
        DELETE FROM results
        WHERE student_id = ? AND exam_id = ?
    """, (student_roll, exam_id))

    # ----------------------------
    # INSERT FRESH RESULT
    # ----------------------------
    cur.execute("""
        INSERT INTO results
        (student_id, exam_id, correct, total, total_questions)
        VALUES (?, ?, ?, ?, ?)
    """, (student_roll, exam_id, correct, total, total))

    conn.commit()
    conn.close()

    print(f"✅ RESULT SAVED: {student_roll} | {correct}/{total}")