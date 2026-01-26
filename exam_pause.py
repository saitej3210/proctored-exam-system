from datetime import datetime
from db import get_db

MAX_PAUSE = 5

def pause_exam(student_id, exam_id):
    conn = get_db()
    conn.row_factory = None
    cur = conn.cursor()

    cur.execute("""
        SELECT status, pause_count
        FROM exam_sessions
        WHERE student_id=? AND exam_id=?
    """, (student_id, exam_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return {"status": "NO_SESSION"}

    status, pause_count = row

    # already paused → do nothing
    if status == "PAUSED":
        conn.close()
        return {"status": "ALREADY_PAUSED", "pause_count": pause_count}

    pause_count = pause_count + 1

    # AUTO SUBMIT
    if pause_count >= MAX_PAUSE:
        cur.execute("""
            UPDATE exam_sessions
            SET status='SUBMITTED', pause_count=?, last_paused_at=?
            WHERE student_id=? AND exam_id=?
        """, (pause_count, datetime.utcnow().isoformat(), student_id, exam_id))

        cur.execute("""
            UPDATE students
            SET status='submitted'
            WHERE id=?
        """, (student_id,))

        conn.commit()
        conn.close()
        return {"status": "AUTO_SUBMITTED", "pause_count": pause_count}

    # NORMAL PAUSE
    cur.execute("""
        UPDATE exam_sessions
        SET status='PAUSED',
            pause_count=?,
            last_paused_at=?
        WHERE student_id=? AND exam_id=?
    """, (pause_count, datetime.utcnow().isoformat(), student_id, exam_id))

    conn.commit()
    conn.close()

    return {"status": "PAUSED", "pause_count": pause_count}