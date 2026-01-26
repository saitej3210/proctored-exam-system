from flask import request
from db import get_db

def check_device_lock(student_id, exam_id):
    ip = request.remote_addr
    ua = request.headers.get("User-Agent")

    conn = get_db()
    cur = conn.cursor()

    # already device lock undaa?
    cur.execute("""
        SELECT ip_address, user_agent
        FROM exam_device_lock
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))

    row = cur.fetchone()

    # first time exam open
    if row is None:
        cur.execute("""
            INSERT INTO exam_device_lock (student_id, exam_id, ip_address, user_agent)
            VALUES (?, ?, ?, ?)
        """, (student_id, exam_id, ip, ua))
        conn.commit()
        conn.close()
        return True   # allow

    # already lock undi → compare
    if row["ip_address"] != ip or row["user_agent"] != ua:
        conn.close()
        return False  # block

    conn.close()
    return True  # same device