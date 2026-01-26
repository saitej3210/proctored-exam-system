print("🔥🔥 THIS FILE IS RUNNING 🔥🔥", __file__)
import re
import time
import os
import sqlite3
import pdfplumber
from db import get_db, init_db
from flask import (
    Flask,
    request,
    redirect,
    render_template,
    session,
    send_from_directory
)

from pathlib import Path
from flask import send_file, Response
import mimetypes
from db import (
    init_db,
    get_db
)
from flask import abort
from flask import send_file

init_db()
from exam_pause import pause_exam
from db_init import init_db
from db import migrate_exam_violations_table
migrate_exam_violations_table()

init_db()

def get_db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn
# --------------------------------
# ONLY for init & migration
# --------------------------------


# --------------------------------
# Runtime DB usage (students, inserts, locks)
# --------------------------------
from db import get_db



# --------------------------------
# APP INIT
# --------------------------------

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "local-dev-key")

# 🔥 RUN ONCE AT START
with app.app_context():
    init_db(),get_db()
   # migrate_questions_table()
   # migrate_students_table()
    # migrate_exam_sessions_timer_pause()   # 👈 THIS LINE IS MISSING NOW
    # migrate_results_table()
    # migrate_exams_table()
# --------------------------------
# Uploads
# --------------------------------
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --------------------------------
# DB INIT (DO NOT DELETE)
# --------------------------------


# --------------------------------
# HOME (OLD UI)
# --------------------------------

# -------------------------------------------------
# HOME (OLD UI)
# -------------------------------------------------




@app.route("/login")
def index():
    return render_template("index.html")

# -------------------------------------------------
# ADMIN LOGIN
# -------------------------------------------------

# -------------------------------------------------
# ADMIN DASHBOARD
# -------------------------------------------------


# -------------------------------------------------
# CREATE EXAM
# -------------------------------------------------
@app.route("/create-exam", methods=["GET", "POST"])
def create_exam():
    if not session.get("admin"):
        return redirect("/admin/login")

    if request.method == "POST":
        exam_name = request.form.get("exam_name")
        subject = request.form.get("subject")
        total_marks = int(request.form.get("total_marks", 0))
        enable_timer = 1 if request.form.get("enable_timer") else 0
        timer_minutes = request.form.get("timer_minutes")
        timer_minutes = int(timer_minutes) if timer_minutes else 0

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO exams (
            exam_name, subject, total_marks,
            timer_minutes, enable_timer, started
        ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            exam_name,
            subject,
            total_marks,
            timer_minutes,
            enable_timer,
            0
        ))

        conn.commit()
        exam_id = cur.lastrowid
        conn.close()

        return redirect(f"/upload-questions/{exam_id}")

    return render_template("create_exam.html")

# -------------------------------------------------
# UPLOAD QUESTIONS (OLD UI)
# -------------------------------------------------

@app.route("/upload-questions/<int:exam_id>", methods=["GET", "POST"])
def upload_questions(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    if request.method == "POST":

        # ==============================
        # 1️⃣ GET FILES
        # ==============================
        qpdf = request.files.get("question_pdf")
        apdf = request.files.get("answer_pdf")

        if not qpdf:
            return "Question PDF missing", 400

        # ==============================
        # 2️⃣ SAVE QUESTION PDF
        # ==============================
        qpath = os.path.join(UPLOAD_FOLDER, f"exam_{exam_id}_questions.pdf")
        qpdf.save(qpath)

        # ==============================
        # 3️⃣ SAVE ANSWER KEY PDF (OPTIONAL)
        # ==============================
        apath = None
        if apdf:
            apath = os.path.join(UPLOAD_FOLDER, f"exam_{exam_id}_answers.pdf")
            apdf.save(apath)

        # ==============================
        # 4️⃣ PARSE QUESTIONS (EXISTING – NO CHANGE)
        # ==============================
        parsed_questions = parse_mcq_pdf(qpath)

        if not parsed_questions:
            return "No questions detected in PDF", 400

        conn = get_db()
        cur = conn.cursor()

        # ==============================
        # 5️⃣ INSERT QUESTIONS (EXISTING – NO CHANGE)
        # ==============================
        for idx, q in enumerate(parsed_questions, start=1):
            cur.execute("""
                INSERT INTO questions
                (exam_id, question_no, question, option_a, option_b, option_c, option_d)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                exam_id,
                idx,
                q["question"],
                q.get("A", ""),
                q.get("B", ""),
                q.get("C", ""),
                q.get("D", "")
            ))

        conn.commit()

        # ==============================
        # 6️⃣ 🔥 AUTO APPLY ANSWER KEY (NEW – SAFE ADD)
        # ==============================
        if apath:
            answer_map = parse_answer_key_pdf(apath)

            for qno, ans in answer_map.items():
                cur.execute("""
                    UPDATE questions
                    SET correct_option = ?
                    WHERE exam_id = ? AND question_no = ?
                """, (ans.lower(), exam_id, qno))

            conn.commit()

        conn.close()

        return redirect(f"/admin/exam/{exam_id}/control")

    # ==============================
    # GET → SHOW PAGE ONLY
    # ==============================
    return render_template("upload_questions.html", exam_id=exam_id)

def parse_mcq_pdf(pdf_path):
    questions = []

    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    blocks = re.split(r"\n\s*\d+\.\s*", text)

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 5:
            continue

        question = lines[0].strip()

        opts = {"A": "", "B": "", "C": "", "D": ""}
        for line in lines[1:]:
            m = re.match(r"[\(\[]?([A-Da-d])[\)\].\-]?\s*(.*)", line)
            if m:
                key = m.group(1).upper()
                opts[key] = m.group(2)

        if all(opts.values()):
            questions.append({
                "question": question,
                "A": opts["A"],
                "B": opts["B"],
                "C": opts["C"],
                "D": opts["D"]
            })

    return questions


def parse_answer_key_pdf(pdf_path):
    import pdfplumber, re

    answers = {}

    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # match: 1) a
    matches = re.findall(r'(\d+)\)\s*([a-d])', text.lower())

    for qno, ans in matches:
        answers[int(qno)] = ans.lower()

    return answers



# -------------------------------------------------
# ADMIN EXAM CONTROL
# -------------------------------------------------








@app.route("/student/join/<int:exam_id>")
def student_join_exam(exam_id):

    if not session.get("student_id"):
        return redirect("/student/login")

    student_id = session["student_id"]

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -----------------------
    # RESET STUDENT STATUS
    # -----------------------
    cur.execute("""
        UPDATE students
        SET status = 'active'
        WHERE id = ? AND exam_id = ?
    """, (student_id, exam_id))

    # -----------------------
    # REGISTER PARTICIPANT
    # -----------------------
    cur.execute("""
        SELECT id FROM exam_participants
        WHERE exam_id = ? AND student_id = ?
    """, (exam_id, student_id))
    exists = cur.fetchone()

    if not exists:
        cur.execute("""
            INSERT INTO exam_participants
            (exam_id, student_id, status, joined_at)
            VALUES (?, ?, 'joined', CURRENT_TIMESTAMP)
        """, (exam_id, student_id))

    # -----------------------
    # START EXAM TIMER (ONLY ONCE)
    # -----------------------
    

    conn.commit()
    conn.close()

    return redirect(url_for("student_exam", exam_id=exam_id))
@app.route("/student/login", methods=["GET"])
def student_login_page():
    return render_template("student/student_login.html")


@app.route("/student/login", methods=["GET", "POST"])
def student_login():

    # --------------------
    # GET : show login page
    # --------------------
    if request.method == "GET":
        return render_template("student/login.html")

    # --------------------
    # POST : login student
    # --------------------
    roll = request.form["roll"]
    name = request.form["name"]
    exam_id = int(request.form["exam_id"])

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --------------------
    # check student exists
    # --------------------
    cur.execute("""
        SELECT * FROM students
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))

    student = cur.fetchone()

    # --------------------
    # FIRST TIME STUDENT
    # --------------------
    if not student:
        cur.execute("""
            INSERT INTO students (
                roll, name, exam_id, status, is_online, left
            )
            VALUES (?, ?, ?, 'waiting', 1, 0)
        """, (roll, name, exam_id))

        conn.commit()
        student_id = cur.lastrowid

    # --------------------
    # EXISTING STUDENT
    # --------------------
    else:
        student_id = student["id"]

        cur.execute("""
            UPDATE students
            SET
                is_online = 1,
                left = 0
            WHERE id = ?
        """, (student_id,))

        conn.commit()

    conn.close()

    # --------------------
    # ✅ SESSION SET (THIS IS CORRECT)
    # --------------------
    session["student"] = {
        "roll": roll,
        "name": name
    }
    session["student_id"] = student_id   # 🔥 VERY IMPORTANT
    session["exam_id"] = exam_id          # 🔥 VERY IMPORTANT

    # --------------------
    # GO TO WAITING PAGE
    # --------------------
    return redirect(f"/student/waiting/{exam_id}")
# -------------------------------------------------
# START EXAM
# -------------------------------------------------

# -------------------------------------------------
# STUDENT LOGIN
# -------------------------------------------------
@app.route("/admin/exam/<int:exam_id>/start")
def start_exam(exam_id):
    import time
    now = int(time.time())

    # ✅ ADD THESE (MISSING PART)
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    UPDATE exam_sessions
    SET status='RUNNING',
     timer_enabled = 1,                -- 🔥 THIS WAS MISSING
     timer_started_at = COALESCE(timer_started_at, ?),
     paused_at = NULL,
     total_paused_seconds = 0
    WHERE exam_id = ?
    """, (now, exam_id))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")



# --------------------------------------------------
# STUDENT START EXAM
# --------------------------------------------------
@app.route("/student/start_exam/<int:exam_id>")
def student_start_exam(exam_id):
    if "student" not in session:
        return redirect("/student/login")

    # 🔥 FIX: exam_id MUST be reset
    session["exam_id"] = exam_id

    print("STUDENT START EXAM SESSION:", session)

    return redirect(f"/student/exam/{exam_id}")

@app.route("/student/init-exam-session", methods=["POST"])
def init_exam_session():
    if "student_id" not in session or "exam_id" not in session:
        return jsonify({"ok": 0})

    student_id = session["student_id"]
    exam_id = session["exam_id"]

    import time
    now = int(time.time())

    conn = get_db()
    cur = conn.cursor()

    # 🔒 create session row ONLY if not exists
    cur.execute("""
        INSERT INTO exam_sessions (student_id, exam_id, status, start_time)
        SELECT ?, ?, 'RUNNING', ?
        WHERE NOT EXISTS (
            SELECT 1 FROM exam_sessions
            WHERE student_id=? AND exam_id=?
        )
    """, (student_id, exam_id, now, student_id, exam_id))

    conn.commit()
    conn.close()

    return jsonify({"ok": 1})



# -------------------------------------------------
# STUDENT WAITING
# -------------------------------------------------


# STUDENT WAITING ROOM (SAFE VERSION)
# ------------------------------------------

@app.route("/student/submitted")
def student_submitted():
    return render_template("student/student_submitted.html")


@app.route("/student/waiting/<int:exam_id>")
def student_waiting(exam_id):
    # ❌ DO NOT check session here
    # ❌ DO NOT redirect to login here
    return render_template("student/student_waiting.html", exam_id=exam_id)
from evaluator import evaluate_exam

@app.route("/admin/exam/<int:exam_id>/release_results", methods=["POST"])
def release_results(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    # get students of this exam
    cur.execute("""
        SELECT roll
        FROM students
        WHERE exam_id = ?
    """, (exam_id,))
    students = cur.fetchall()

    # evaluate each student ONCE
    for s in students:
        evaluate_exam(s["roll"], exam_id)

    # mark results released
    cur.execute("""
        UPDATE exams
        SET results_released = 1
        WHERE id = ?
    """, (exam_id,))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")

@app.route("/student/check-results-status")
def check_results_status():
    if "exam_id" not in session:
        return jsonify({"status":"LOGOUT"})

    exam_id = session["exam_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT results_released FROM exams WHERE id = ?",
        (exam_id,)
    )
    exam = cur.fetchone()
    conn.close()

    if exam and exam["results_released"] == 1:
        return jsonify({"status":"RELEASED"})

    return jsonify({"status":"WAIT"})

# -------------------------------------------------
# STUDENT EXAM (DB QUESTIONS)
# -------------------------------------------------
# --------------------------------------------------
# STUDENT EXAM PAGE
# --------------------------------------------------
from flask import render_template, redirect, session, request
from flask import Flask, render_template, request, redirect, url_for
import time


@app.route("/admin/allow-rejoin/<int:exam_id>/<roll>", methods=["POST"])
def allow_rejoin(exam_id, roll):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE students
        SET status = 'in_exam'
        WHERE exam_id = ? AND roll = ?
    """, (exam_id, roll))
    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")

@app.route("/student/leave", methods=["POST"])
def student_leave():
    student_id = session.get("student_id")
    exam_id = session.get("exam_id")

    if student_id and exam_id:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE students
            SET left = 1, status = 'waiting'
            WHERE id = ?
        """, (student_id,))
        conn.commit()
        conn.close()

    session.clear()
    return jsonify({"ok": True})
@app.route("/student/leave_exam/<int:exam_id>", methods=["POST"])
def student_leave_exam(exam_id):
    if "student" not in session:
        return redirect("/student/login")

    roll = session["student"]["roll"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE students
        SET status = 'left_exam'
        WHERE exam_id = ? AND roll = ?
    """, (exam_id, roll))
    conn.commit()
    conn.close()

    session.clear()
    return redirect("/student/login")


 


@app.route("/student/ping", methods=["POST"])
def student_ping():
    if "student" not in session:
        return "", 204

    roll = session["student"]["roll"]
    exam_id = session["exam_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE students
        SET last_ping = strftime('%s','now'),
            status = 'in_exam'
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))
    conn.commit()
    conn.close()

    return "", 204

@app.route("/student/left", methods=["POST"])
def student_left():
    if "student" in session and "exam_id" in session:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE students
            SET status = 'left'
            WHERE roll = ? AND exam_id = ?
        """, (session["student"]["roll"], session["exam_id"]))
        conn.commit()
        conn.close()
    return "", 204



@app.route("/student/status")
def student_status():
    exam_id = session.get("exam_id")
    student = session.get("student")

    if not exam_id or not student:
        return {"status": "WAIT"}  # ❗ NEVER LOGOUT

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT started FROM exams WHERE id = ?", (exam_id,))
    exam = cur.fetchone()

    cur.execute("""
        SELECT status
        FROM students
        WHERE roll = ? AND exam_id = ? AND removed = 0
    """, (student["roll"], exam_id))
    row = cur.fetchone()

    conn.close()

    if not row:
        return {"status": "WAIT"}

    if row["status"] == "paused":
        return {"status": "paused"}

    if row["status"] == "approved" and exam and exam["started"] == 1:
        return {"status": "START"}

    return {"status": "WAIT"}
# STUDENT SUBMIT
# -------------------------------------------------
from evaluator import evaluate_exam

@app.route("/student/submit_exam", methods=["POST"])
def submit_exam():

    student_id = session.get("student_id")
    exam_id = session.get("exam_id")

    if not student_id or not exam_id:
        print("❌ SESSION LOST AT SUBMIT")
        return redirect("/student/login")

    conn = get_db()
    cur = conn.cursor()

    # 🔥 Evaluate exam
    from evaluator import evaluate_exam
    evaluate_exam(student_id, exam_id)

    # 🔥 Update exam status
    cur.execute("""
        UPDATE exam_sessions
        SET status = 'SUBMITTED'
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))

    conn.commit()
    conn.close()

    print("✅ EXAM SUBMITTED, SESSION OK")

    # 🚀 Golden flow
    return render_template("student/wait_for_results.html")


@app.route("/student/wait-for-results")
def wait_for_results():
    if "student" not in session:
        return redirect("/student/login")

    return render_template("student/wait_for_results.html")    





@app.route("/student/done")
def student_done():

    if not session.get("student"):
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, exam_id
        FROM students
        WHERE roll = ?
        ORDER BY id DESC
        LIMIT 1
    """, (session["student"]["roll"],))

    row = cur.fetchone()
    conn.close()

    if not row:
        return "Student not found", 400

    student_id = row["id"]
    exam_id = row["exam_id"]   # 🔥 CORRECT EXAM ID

    result = evaluate_exam(student_id, exam_id)

    return render_template(
        "student/student_done.html",
        result=result
    )




# -------------------------------------------------
# STUDENT RESULT
# -------------------------------------------------
@app.route("/student/result")
def student_result():

    if "student" not in session or "exam_id" not in session:
        return redirect("/student/login")

    exam_id = session["exam_id"]
    roll = session["student"]["roll"]

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔐 STRICT CHECK
    cur.execute(
        "SELECT results_released FROM exams WHERE id = ?",
        (exam_id,)
    )
    exam = cur.fetchone()

    if not exam or exam["results_released"] != 1:
        conn.close()
        return redirect("/student/wait-for-results")

    # ✅ ONLY AFTER RELEASE
    cur.execute("""
        SELECT r.correct, r.total
        FROM results r
        JOIN students s ON s.id = r.student_id
        WHERE s.roll = ? AND r.exam_id = ?
    """, (roll, exam_id))

    result = cur.fetchone()
    conn.close()

    if not result:
        return "Result not found", 404

    return render_template(
        "student/student_result.html",
        correct=result["correct"],
        total=result["total"]
    )
# -------------------------------------------------
# ADMIN RESULTS
# -------------------------------------------------
@app.route('/admin/exam/<int:exam_id>/results')
def admin_exam_results(exam_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        s.roll,
        s.name,
        r.correct,
        r.total,
        (r.correct * 1) AS marks
    FROM results r
    JOIN students s ON r.student_id = s.id
    WHERE r.exam_id = ?
""", (exam_id,))
    results = cur.fetchall()
    conn.close()

    return render_template(
        "admin/exam_results.html",
        results=results,
        exam_id=exam_id
    )
@app.route("/admin/exam/<int:exam_id>/results")
def admin_results(exam_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            s.roll AS roll,
            s.name AS name,
            SUM(CASE 
                WHEN sa.selected_option = q.correct_option THEN 1 
                ELSE 0 
            END) AS correct,
            COUNT(q.id) AS total
        FROM student_answers sa
        JOIN questions q 
            ON sa.question_no = q.id
        JOIN students s 
            ON sa.student_id = s.roll
        WHERE sa.exam_id = ?
        GROUP BY s.roll, s.name
    """, (exam_id,))

    results = cur.fetchall()
    conn.close()

    return render_template(
        "admin_results.html",
        results=results,
        exam_id=exam_id
    )





@app.route("/admin/exam/<int:exam_id>/results")
def view_results(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    return f"Results page for exam {exam_id} (implement later)"

@app.route("/student/thanks")
def student_thanks():
    return render_template("student/student_thanks.html")
# -------------------------------------------------
# SERVE UPLOADS
# -------------------------------------------------
@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)




from flask import jsonify, session   # ⚠️ make sure jsonify import undi

@app.route("/exam/status/<int:exam_id>")
def exam_status(exam_id):

    student = session.get("student")
    if not student:
        return jsonify({"status": "LOGOUT"})

    roll = student["roll"]

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, removed
        FROM students
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))
    student_row = cur.fetchone()

    if not student_row:
        conn.close()
        return jsonify({"status": "LOGOUT"})

    student_id = student_row["id"]

    # 🚨 removed always wins
    if student_row["removed"] == 1:
        conn.close()
        return jsonify({"status": "REMOVED"})

    cur.execute("""
        SELECT status
        FROM exam_sessions
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))
    session_row = cur.fetchone()

    conn.close()

    if not session_row:
        return jsonify({"status": "NOT_STARTED"})

    status = session_row["status"]

    if status in ("PAUSED", "REMOVED", "SUBMITTED", "RUNNING"):
        return jsonify({"status": status})

    return jsonify({"status": "UNKNOWN"})



@app.route("/student/violation", methods=["POST"])
def student_violation():

    student = session.get("student")
    if not student:
        return "", 401

    roll = student["roll"]
    exam_id = student.get("exam_id")

    conn = get_db()
    cur = conn.cursor()

    # 🔴 THIS IS THE FIX
    cur.execute("""
        UPDATE students
        SET status = 'paused'
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))

    conn.commit()
    conn.close()

    return "", 200


@app.route("/exam/ping", methods=["POST"])
def exam_ping():
    student = session.get("student")
    if not student:
        return {"ok": False}

    data = request.get_json()
    exam_id = data.get("exam_id")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exam_sessions
        SET last_ping = strftime('%s','now')
        WHERE student_id = (
            SELECT id FROM students WHERE roll = ? AND exam_id = ?
        )
        AND exam_id = ?
    """, (student["roll"], exam_id, exam_id))

    conn.commit()
    conn.close()

    return {"ok": True}

from flask import jsonify

from datetime import datetime

@app.route("/student/exam-paused/<int:exam_id>")
def student_exam_paused(exam_id):
    if not session.get("student"):
        return redirect("/student/login")

    return render_template(
        "student/exam_paused.html",
        exam_id=exam_id
    )

# -------------------------------------------------
# ADMIN EXAM CONTROL
# -------------------------------------------------    
@app.route("/admin/exam/<int:exam_id>/control")
def admin_exam_control(exam_id):

    # --------------------
    # Admin check
    # --------------------
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --------------------
    # Fetch students + status
    # --------------------
    cur.execute("""
        SELECT
            s.id AS student_id,
            s.roll,
            s.name,
            CASE
                WHEN s.is_online = 0 THEN 'left'
                ELSE s.status
            END AS student_status,
            COALESCE(es.status, 'NOT_STARTED') AS exam_status,
            (
                SELECT COUNT(*)
                FROM exam_violations v
                WHERE v.student_id = s.id
                  AND v.exam_id = ?
            ) AS violation_count
        FROM students s
        LEFT JOIN exam_sessions es
          ON es.student_id = s.id
         AND es.exam_id = ?
        WHERE s.exam_id = ?
    """, (exam_id, exam_id, exam_id))

    students = cur.fetchall()

    # --------------------
    # Fetch exam started flag
    # --------------------
    cur.execute(
        "SELECT started FROM exams WHERE id = ?",
        (exam_id,)
    )
    exam = cur.fetchone()
    exam_started = exam["started"] if exam else 0

    conn.close()

    # --------------------
    # Render control panel
    # --------------------
    return render_template(
        "exam_control.html",
        exam_id=exam_id,
        students=students,
        exam_started=exam_started   # ✅ IMPORTANT FIX
    )
@app.route("/admin/remove-student/<int:exam_id>/<roll>", methods=["POST"])
def admin_remove_student(exam_id, roll):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    # get student
    cur.execute("""
        SELECT id FROM students
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))
    row = cur.fetchone()

    if row:
        student_id = row[0]

        # mark exam session as REMOVED (important)
        cur.execute("""
            UPDATE exam_sessions
            SET status = 'REMOVED'
            WHERE student_id = ? AND exam_id = ?
        """, (student_id, exam_id))

        # delete student record
        cur.execute("""
            DELETE FROM students WHERE id = ?
        """, (student_id,))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")


@app.route("/admin/remove-student/<int:exam_id>/<roll>", methods=["POST"])
def remove_student(exam_id, roll):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    # get student id
    cur.execute("""
        SELECT id FROM students
        WHERE exam_id = ? AND roll = ?
    """, (exam_id, roll))
    row = cur.fetchone()

    if row:
        student_id = row["id"]

        # mark removed
        cur.execute("""
            UPDATE students
            SET removed = 1, status = 'removed'
            WHERE id = ?
        """, (student_id,))

        # 🔥 THIS IS THE KEY FIX 🔥
        cur.execute("""
            UPDATE exam_sessions
            SET status = 'REMOVED'
            WHERE student_id = ? AND exam_id = ?
        """, (student_id, exam_id))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")

@app.route("/student/exam/<int:exam_id>", methods=["GET", "POST"])
def student_exam(exam_id):
    session["exam_id"] = exam_id
    student_id = session.get("student_id")
    if not student_id:
        return redirect("/student/login")
    
    session["exam_id"] = exam_id

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ==================================================
    # 🆕 SAFE ADD — CREATE exam_sessions ROW ONCE
    # (DOES NOT RESET start_time on refresh / resume)
    # ==================================================
    import time
    cur.execute("""
        INSERT INTO exam_sessions (student_id, exam_id, start_time, status)
        SELECT ?, ?, ?, 'RUNNING'
        WHERE NOT EXISTS (
            SELECT 1 FROM exam_sessions
            WHERE student_id = ? AND exam_id = ?
        )
    """, (
        student_id,
        exam_id,
        int(time.time()),
        student_id,
        exam_id
    ))
    
    # ==================================================
    # 🆕 END SAFE ADD
    # ==================================================

    # ==================================================
    # PHASE 2 RULE: exam must be RUNNING
    # ==================================================
    cur.execute("""
        SELECT status
        FROM exam_sessions
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))
    exam_row = cur.fetchone()

    if not exam_row or exam_row["status"] != "RUNNING":
        conn.close()
        return redirect(f"/student/waiting/{exam_id}")

    # ==================================================
    # LOAD QUESTIONS
    # ==================================================
    cur.execute("""
        SELECT
            question_no,
            question,
            option_a,
            option_b,
            option_c,
            option_d
        FROM questions
        WHERE exam_id = ?
        ORDER BY question_no ASC
    """, (exam_id,))
    question_rows = cur.fetchall()

    # ✅ ⭐ IMPORTANT FIX ⭐
    # sqlite Row → normal dict (JSON safe)
    questions = [
        {
            "question_no": q["question_no"],
            "question": q["question"],
            "option_a": q["option_a"],
            "option_b": q["option_b"],
            "option_c": q["option_c"],
            "option_d": q["option_d"],
        }
        for q in question_rows
    ]

    # ==================================================
    # LOAD SAVED ANSWERS
    # ==================================================
    cur.execute("""
        SELECT question_no, selected_option
        FROM student_answers
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))
    saved_rows = cur.fetchall()

    saved_answers = {
        row["question_no"]: row["selected_option"]
        for row in saved_rows
    }
    # 🔒 SAFE: Create exam session ONLY if not exists
    cur.execute("""
     SELECT id FROM exam_sessions
     WHERE exam_id = ? AND student_id = ?
    """, (exam_id, student_id))

    exists = cur.fetchone()

    if not exists:
     cur.execute("""
        INSERT INTO exam_sessions (
            exam_id,
            student_id,
            status,
            timer_enabled,
            exam_duration,
            timer_started_at
        )
        SELECT
            ?,
            ?,
            'RUNNING',
            1,
            duration * 60,
            strftime('%s','now')
        FROM exams
        WHERE id = ?
    """, (exam_id, student_id, exam_id))

    conn.commit()
    conn.close()

    return render_template(
        "student/student_exam.html",
        exam_id=exam_id,
        student_id=student_id,
        questions=questions,
        saved_answers=saved_answers
    )

from datetime import datetime
from device_guard import check_device_lock   # 🔴 ADD 1


from datetime import datetime
import sqlite3
from flask import session, redirect, render_template, request

from flask import jsonify

@app.route("/admin/exam/<int:exam_id>/resume/<int:student_id>")
def resume_exam(exam_id, student_id):
    conn = get_db()
    cur = conn.cursor()

    import time

    # 🔥 STEP-3A: calculate paused time
    row = cur.execute("""
        SELECT paused_at, paused_seconds
        FROM exam_sessions
        WHERE exam_id = ? AND student_id = ?
    """, (exam_id, student_id)).fetchone()

    if row and row["paused_at"]:
        paused_duration = int(time.time()) - int(row["paused_at"])

        cur.execute("""
            UPDATE exam_sessions
            SET paused_seconds = paused_seconds + ?
            WHERE exam_id = ? AND student_id = ?
        """, (paused_duration, exam_id, student_id))

    # ✅ EXISTING CODE (unchanged)
    cur.execute("""
        UPDATE exam_sessions
        SET status='RUNNING',
            paused=0,
            resume_allowed=1,
            paused_at=NULL
        WHERE exam_id=? AND student_id=?
    """, (exam_id, student_id))

    conn.commit()
    conn.close()

    return jsonify({"resumed": 1})



@app.route("/exam/progress", methods=["POST"])
def exam_progress():
    data = request.json
    student_id = data.get("student_id")
    exam_id = data.get("exam_id")
    last_q = data.get("last_question")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exam_sessions
        SET last_question = ?
        WHERE student_id = ? AND exam_id = ? AND status = 'RUNNING'
    """, (last_q, student_id, exam_id))

    conn.commit()
    conn.close()

    return jsonify({"ok": True})

from datetime import datetime



@app.route("/device", methods=["GET", "POST"])
def device_select():
    if request.method == "POST":
        session["device"] = request.form.get("device")
        return redirect("/student/login")
    return render_template("device_select.html")


@app.route("/home")
def home():
    if "mode" not in session:
        return redirect("/")

    return render_template("home.html")


@app.route("/")
def splash():
    session.clear()   # 🔥 VERY IMPORTANT
    return render_template("splash.html")



@app.route("/mobile/student/login")
def mobile_student_login():
    return render_template("mobile/student/student_login.html")


@app.route("/choose-device")
def choose_device():
    return render_template("choose_device.html")


@app.route("/desktop")
def desktop_home():
    return render_template("home.html")  # already undi


@app.route("/mobile")
def mobile_home():
    return render_template("mobile/student/home.html")


@app.route("/admin-login")
def admin_login_alias():
    return redirect("/admin/login")


@app.route("/admin-dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect("/admin/login")

    ui = session.get("ui")

    if ui == "mobile":
        return render_template("mobile/admin/admin_dashboard.html")
    else:
        return render_template("admin/admin_dashboard.html")

@app.route("/")
def mode_select():
    return render_template("mode_select.html")


@app.route("/set-ui/<mode>")
def set_ui(mode):
    if mode in ["desktop", "mobile"]:
        session.clear()           # 🔥 important
        session["ui"] = mode
    return redirect("/admin/login")

@app.route("/select/desktop")
def select_desktop():
    session["mode"] = "desktop"
    return redirect("/home")

@app.route("/select/mobile")
def select_mobile():
    session["mode"] = "mobile"
    return redirect("/home")

@app.route("/mobile/admin-dashboard")
def admin_dashboard_mobile():
    if not session.get("admin"):
        return redirect("/admin/login")
    return render_template("mobile/admin/admin_dashboard.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin":
            session["admin"] = True
            return redirect("/admin-dashboard")
    return render_template("admin_login.html")

@app.route("/admin/exam/<int:exam_id>/analytics")
def admin_exam_analytics(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ============================
    # STEP 1: TOTAL STUDENTS
    # ============================
    cur.execute("""
        SELECT COUNT(DISTINCT student_id) AS total_students
        FROM student_answers
        WHERE exam_id = ?
    """, (exam_id,))
    total_students = cur.fetchone()["total_students"] or 0

    # ============================
    # STEP 2: SCORES (AVG / HIGH / LOW)
    # ============================
    cur.execute("""
    SELECT
       sa.student_id,
         SUM(
           CASE
              WHEN sa.selected_option = q.correct_option THEN 1
              ELSE 0
           END
        ) AS score
    FROM student_answers sa
    JOIN questions q
      ON q.exam_id = sa.exam_id
     AND q.question_no = sa.question_no
    WHERE sa.exam_id = ?
    GROUP BY sa.student_id
    """, (exam_id,))

    rows = cur.fetchall()

    scores = []
    for row in rows:
      score = row["score"] if row["score"] is not None else 0
      scores.append(int(score))

    if scores:
      average = round(sum(scores) / len(scores), 2)
      highest = max(scores)
      lowest = min(scores)
    else:
      average = 0.0
      highest = 0
      lowest = 0

    # ============================
    # STEP 3: LEADERBOARD
    # ============================
    cur.execute("""
        SELECT
            s.roll,
            s.name,
            SUM(
                CASE
                    WHEN sa.selected_option = q.correct_option THEN 1
                    ELSE 0
                END
            ) AS marks
        FROM student_answers sa
        JOIN students s ON s.id = sa.student_id
        JOIN questions q
            ON q.exam_id = sa.exam_id
           AND q.question_no = sa.question_no
        WHERE sa.exam_id = ?
        GROUP BY sa.student_id
        ORDER BY marks DESC
    """, (exam_id,))
    leaderboard = cur.fetchall()

    # ============================
    # STEP 4: HARDEST & EASIEST
    # ============================
    cur.execute("""
        SELECT
            q.question_no,
            q.question,
            SUM(
                CASE
                    WHEN sa.selected_option = q.correct_option THEN 1
                    ELSE 0
                END
            ) AS correct_count
        FROM questions q
        LEFT JOIN student_answers sa
            ON sa.question_no = q.question_no
           AND sa.exam_id = q.exam_id
        WHERE q.exam_id = ?
        GROUP BY q.question_no
        ORDER BY correct_count ASC
        LIMIT 1
    """, (exam_id,))
    hardest = cur.fetchone()

    cur.execute("""
        SELECT
            q.question_no,
            q.question,
            SUM(
                CASE
                    WHEN sa.selected_option = q.correct_option THEN 1
                    ELSE 0
                END
            ) AS correct_count
        FROM questions q
        LEFT JOIN student_answers sa
            ON sa.question_no = q.question_no
           AND sa.exam_id = q.exam_id
        WHERE q.exam_id = ?
        GROUP BY q.question_no
        ORDER BY correct_count DESC
        LIMIT 1
    """, (exam_id,))
    easiest = cur.fetchone()

    # ============================
    # STEP 5: QUESTION-WISE ANALYTICS
    # ============================
     # ==============================
# QUESTION-WISE ANALYSIS
# ==============================
   # ===============================
    # QUESTION WISE ANALYTICS (FINAL)
    # ===============================
    cur.execute("""
    SELECT
      q.question_no,
      q.question,
      COUNT(sa.id) AS attempts,
     SUM(CASE WHEN sa.selected_option = q.correct_option THEN 1 ELSE 0 END) AS correct,
     SUM(CASE WHEN sa.selected_option != q.correct_option THEN 1 ELSE 0 END) AS wrong
     FROM questions q
     LEFT JOIN student_answers sa
      ON sa.exam_id = q.exam_id
     AND sa.question_no = q.question_no
    WHERE q.exam_id = ?
    GROUP BY q.question_no, q.question
    ORDER BY q.question_no
    """, (exam_id,))

    rows = cur.fetchall()

    question_integrity = []
    question_chart_data = []

    for r in rows:
     attempts = r["attempts"] or 0
     correct = r["correct"] or 0
     wrong = r["wrong"] or 0
     accuracy = round((correct / attempts) * 100, 2) if attempts > 0 else 0

     question_integrity.append({
        "question_no": r["question_no"],
        "question": r["question"],
        "attempts": attempts,
        "correct": correct,
        "wrong": wrong,
        "accuracy": accuracy
    })

     question_chart_data.append({
        "label": f"Q{r['question_no']}",
        "correct": correct,
        "wrong": wrong
     })
    
# ============================
# STEP 6: VIOLATION ANALYTICS (FINAL – COPY THIS FULL)
# ============================
# ============================
# STEP 6: VIOLATION ANALYTICS (FINAL – FIXED)
# ============================

# ---------- TOTAL VIOLATIONS ----------
    cur.execute("""
     SELECT COUNT(*) AS total
     FROM exam_violations
     WHERE exam_id = ?
    """, (exam_id,))
    total_violations = cur.fetchone()["total"] or 0

     # paused student (latest paused)
    cur.execute("""
     SELECT student_id
     FROM exam_student_status
     WHERE exam_id = ?
      AND status = 'PAUSED'
     ORDER BY updated_at DESC
     LIMIT 1
    """, (exam_id,))

    row = cur.fetchone()
    paused_student_id = row["student_id"] if row else None
# ---------- TOP VIOLATOR ----------
    cur.execute("""
     SELECT s.roll, s.name, COUNT(v.id) AS violation_count
     FROM exam_violations v
     JOIN students s ON s.id = v.student_id
     WHERE v.exam_id = ?
     GROUP BY v.student_id
     ORDER BY violation_count DESC
     LIMIT 1
    """, (exam_id,))
    top_violator = cur.fetchone()

    
# ---------- EVENT-WISE COUNTS ----------
    cur.execute("""
     SELECT LOWER(event_type) AS event_type, COUNT(*) AS count
     FROM exam_violations
     WHERE exam_id = ?
     GROUP BY LOWER(event_type)
    """, (exam_id,))

    rows = cur.fetchall()


# ---------- TABLE DATA (LIST) ----------
    violation_stats = []
    for r in rows:
      violation_stats.append({
        "event_type": r["event_type"].upper(),
        "count": r["count"]
    })


# ---------- CHART DATA (DICT) ----------
    event_counts = {
      "tab_switch": 0,
      "blur": 0,
      "copy": 0,
      "paste": 0,
      "multiple_faces": 0,
      "mobile_detected": 0
    }

    for r in rows:
     event_counts[r["event_type"]] = r["count"]

    # TOTAL QUESTIONS IN EXAM
    cur.execute("""
      SELECT COUNT(*) AS total_qs
      FROM questions
      WHERE exam_id = ?
    """, (exam_id,))
    total_questions = cur.fetchone()["total_qs"]
    # ============================
    # STEP 7: STUDENT-WISE PERFORMANCE
    # ============================
    cur.execute("""
        SELECT
            sa.student_id,
            s.roll,
            s.name,
            COUNT(DISTINCT sa.question_no) AS total,
            SUM(
                CASE
                    WHEN sa.selected_option = q.correct_option THEN 1
                    ELSE 0
                END
            ) AS score
        FROM student_answers sa
        JOIN students s ON s.id = sa.student_id
        JOIN questions q
            ON q.exam_id = sa.exam_id
           AND q.question_no = sa.question_no
        WHERE sa.exam_id = ?
        GROUP BY sa.student_id
    """, (exam_id,))

    student_stats = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT student_id, COUNT(*) AS violations
        FROM exam_violations
        WHERE exam_id = ?
        GROUP BY student_id
    """, (exam_id,))
    violation_map = {r["student_id"]: r["violations"] for r in cur.fetchall()}

    for s in student_stats:
        s["violations"] = violation_map.get(s["student_id"], 0)
        s["total"] = total_questions
    # ============================
    # STEP 8: AI CHEATING RISK (FINAL)
    # ============================
    cheating_risk = []
    risk_summary = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}

    for s in student_stats:
        v = s["violations"]
        score = s["score"]

        if v >= 5 or (v >= 3 and score >= 8):
            risk = "HIGH"
        elif v >= 2:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        cheating_risk.append({
            "roll": s["roll"],
            "name": s["name"],
            "risk": risk
        })
        risk_summary[risk] += 1

    # ============================
    # STEP 9: TIME-BASED ANALYTICS
    # ============================
    # =========================
# TIME BASED QUESTION ANALYSIS
# =========================
    # ==============================
# STEP X: TIME BASED QUESTION ANALYSIS
# ==============================

    cur.execute("""
    SELECT
        q.question_no,
        ROUND(AVG(COALESCE(sa.time_taken, 0)), 2) AS avg_time_spent,
        MIN(COALESCE(sa.time_taken, 0)) AS fastest,
        MAX(COALESCE(sa.time_taken, 0)) AS slowest,
        ROUND(AVG(COALESCE(sa.time_taken, 0)), 2) AS avg_duration
    FROM questions q
    LEFT JOIN student_answers sa
        ON sa.question_no = q.question_no
       AND sa.exam_id = ?
    WHERE q.exam_id = ?
    GROUP BY q.question_no
    ORDER BY q.question_no
    """, (exam_id, exam_id))

    time_based_analysis = cur.fetchall()
      
    # ============================
    # STEP 10: PROCTORING INTELLIGENCE
    # ============================
    proctoring_insights = []

    for s in student_stats:
        risk_score = (s["violations"] * 2)
        if risk_score >= 10:
            level = "HIGH"
        elif risk_score >= 5:
            level = "MEDIUM"
        else:
            level = "LOW"

        proctoring_insights.append({
         "student_id": s["student_id"],
         "roll": s["roll"],
         "name": s["name"],
         "risk_score": risk_score,
         "level": level
        })

    # ==============================
# STEP 11: QUESTION INTEGRITY ANALYSIS
# ==============================


   
    
# =========================
# CHEATING RISK DISTRIBUTION
# =========================

   # =========================
# CHEATING RISK (DERIVED)
# =========================

    # =========================
# CHEATING RISK DISTRIBUTION
# =========================
    # =============================
# CHEATING RISK DISTRIBUTION
# =============================
    # ---------- CHEATING RISK DISTRIBUTION (SAFE DEFAULT) ----------
    

    # ================= CHEATING RISK DISTRIBUTION =================
    cur.execute("""
     SELECT event_type, COUNT(*) as cnt
     FROM exam_violations
     WHERE exam_id = ?
     GROUP BY event_type
     """, (exam_id,))

    rows = cur.fetchall()

    low = medium = high = 0

    for r in rows:
     event = r["event_type"].lower()   # <<< IDHI ADD CHEYYALI

     if event in ("tab_switch", "blur"):
        low += r["cnt"]
     elif event in ("copy", "paste"):
        medium += r["cnt"]
     elif event in ("multiple_faces", "mobile_detected"):
        high += r["cnt"]

    cheating_risk = {
     "low": low,
     "medium": medium,
     "high": high
    }
    # SAFE DEFAULT (MUST)
    event_counts = {
     "tab_switch": 0,
      "blur": 0,
      "copy": 0,
      "paste": 0,
      "multiple_faces": 0,
      "mobile_detected": 0
    }

    cur.execute("""
     SELECT event_type, COUNT(*) as cnt
     FROM exam_violations
     WHERE exam_id = ?
     GROUP BY event_type
    """, (exam_id,))

    rows = cur.fetchall()

    for r in rows:
     key = r["event_type"].lower()
     if key in event_counts:
        event_counts[key] = r["cnt"]

    cur.execute("""
     SELECT roll
     FROM students
     WHERE id = ?
    """, (paused_student_id,))
    row = cur.fetchone()
    paused_student_roll = row["roll"] if row else None 

    cur.execute("""
     SELECT
        s.id AS student_id,
        s.name,
        s.roll,
        es.status,
        es.paused,
        es.resume_allowed
     FROM exam_sessions es
     JOIN students s ON s.id = es.student_id
     WHERE es.exam_id = ?
      AND es.paused = 1
     """, (exam_id,))
    paused_students = cur.fetchall()
    conn.close()

    return render_template(
        "admin_exam_analytics.html",
        exam_id=exam_id,
        total_students=total_students,
        average=average,
        highest=highest,
        lowest=lowest,
        leaderboard=leaderboard,
        hardest=hardest,
        easiest=easiest,
        total_violations=total_violations,
        top_violator=top_violator,
        student_stats=student_stats,
        risk_summary=risk_summary,
        time_based_analysis=time_based_analysis,
        proctoring_insights=proctoring_insights,
        question_chart_data=question_chart_data,
        cheating_risk=cheating_risk ,
        question_integrity=question_integrity,
        question_wise=question_integrity,
        event_counts=event_counts,
        violation_stats=violation_stats,
        paused_student_id=paused_student_id,
        paused_students=paused_students
        
        
        
    )

@app.route("/admin/exam/<int:exam_id>/export/csv")
def export_exam_csv(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            s.roll,
            s.name,
            r.correct AS score,
            r.total AS total_questions,
            COUNT(v.id) AS violations
        FROM results r
        JOIN students s ON s.id = r.student_id
        LEFT JOIN exam_violations v
          ON v.student_id = s.id AND v.exam_id = ?
        WHERE r.exam_id = ?
        GROUP BY s.id
    """, (exam_id, exam_id))

    rows = cur.fetchall()
    conn.close()

    import csv
    from io import StringIO
    from flask import Response

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Roll", "Name", "Score", "Total", "Violations"])
    for r in rows:
        writer.writerow([
            r["roll"],
            r["name"],
            r["score"],
            r["total_questions"],
            r["violations"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment;filename=exam_{exam_id}_results.csv"
        }
    )

@app.route("/admin/exam/<int:exam_id>/export/pdf")
def export_exam_pdf(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from io import BytesIO
    from flask import send_file

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, f"Exam Analytics Report – Exam {exam_id}")
    y -= 40

    pdf.setFont("Helvetica", 12)

    def line(text):
        nonlocal y
        pdf.drawString(50, y, text)
        y -= 20

    line(f"Total Students : {total_students}")
    line(f"Average Score  : {average}")
    line(f"Highest Score  : {highest}")
    line(f"Lowest Score   : {lowest}")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"exam_{exam_id}_analytics.pdf",
        mimetype="application/pdf"
    )

@app.route("/admin/exam/<int:exam_id>/timeline")
def admin_exam_timeline(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    student_id = request.args.get("student_id")  # 👈 NEW (optional)

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if student_id:
        cur.execute("""
            SELECT
                s.roll,
                s.name,
                v.event_type,
                v.created_at
            FROM exam_violations v
            JOIN students s ON s.id = v.student_id
            WHERE v.exam_id = ?
              AND v.student_id = ?
            ORDER BY v.created_at DESC
        """, (exam_id, student_id))
    else:
        cur.execute("""
            SELECT
                s.roll,
                s.name,
                v.event_type,
                v.created_at
            FROM exam_violations v
            JOIN students s ON s.id = v.student_id
            WHERE v.exam_id = ?
            ORDER BY v.created_at DESC
        """, (exam_id,))

    timeline = cur.fetchall()

    # 👇 dropdown data
    cur.execute("""
        SELECT id, roll, name
        FROM students
        WHERE exam_id = ?
    """, (exam_id,))
    students = cur.fetchall()
   
    conn.close()

    return render_template(
        "admin_exam_timeline.html",
        exam_id=exam_id,
        timeline=timeline,
        students=students,
        selected_student=student_id
    ) 
@app.route("/admin/exam/<int:exam_id>/export")
def export_exam_results(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT s.roll, s.name, r.correct, r.total_questions
        FROM results r
        JOIN students s ON s.id = r.student_id
        WHERE r.exam_id = ?
        ORDER BY r.correct DESC
    """, (exam_id,))

    rows = cur.fetchall()
    conn.close()

    import csv
    from io import StringIO
    from flask import Response

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Roll", "Name", "Score", "Total"])

    for r in rows:
        cw.writerow([r["roll"], r["name"], r["correct"], r["total_questions"]])

    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment;filename=exam_{exam_id}_results.csv"
        }
    )
@app.route("/admin/exam/<int:exam_id>/analytics")
def exam_analytics(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # total students who have results
    cur.execute("""
        SELECT COUNT(*) FROM results
        WHERE exam_id = ?
    """, (exam_id,))
    total_students = cur.fetchone()[0]

    # average score
    # average score
    cur.execute("""
      SELECT AVG(correct) AS avg_score
      FROM results
      WHERE exam_id = ?
    """, (exam_id,))

    row = cur.fetchone()
    avg_score = row["avg_score"] if row and row["avg_score"] is not None else 0
    average = round(float(avg_score), 2)

    # highest score
    cur.execute("""
      SELECT MAX(correct)
      FROM results
      WHERE exam_id = ?
    """, (exam_id,))
    highest = cur.fetchone()[0] or 0

# lowest score
    cur.execute("""
      SELECT MIN(correct)
      FROM results
      WHERE exam_id = ?
    """, (exam_id,))
    lowest = cur.fetchone()[0] or 0
    # ==============================
# QUESTION-WISE ANALYTICS (STEP 8)
# ==============================

    
    # 🔥 MARKS DISTRIBUTION (STEP-5 CORE)
    cur.execute("""
        SELECT
            SUM(CASE WHEN correct BETWEEN 0 AND 2 THEN 1 ELSE 0 END) AS r0_2,
            SUM(CASE WHEN correct BETWEEN 3 AND 5 THEN 1 ELSE 0 END) AS r3_5,
            SUM(CASE WHEN correct BETWEEN 6 AND 8 THEN 1 ELSE 0 END) AS r6_8,
            SUM(CASE WHEN correct BETWEEN 9 AND 10 THEN 1 ELSE 0 END) AS r9_10
        FROM results
        WHERE exam_id = ?
    """, (exam_id,))

    dist = cur.fetchone()
    conn.close()

    return render_template(
        "admin_exam_analytics.html",
        exam_id=exam_id,
        total_students=total_students,
        avg_score=avg_score,
        highest=highest,
        lowest=lowest,
        dist=dist
    )

@app.route("/admin/exam/<int:exam_id>/question-analytics")
def admin_question_analytics(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            sa.question_no,
            q.question,
            q.correct_option,
            SUM(CASE WHEN sa.selected_option = 'a' THEN 1 ELSE 0 END) AS a_count,
            SUM(CASE WHEN sa.selected_option = 'b' THEN 1 ELSE 0 END) AS b_count,
            SUM(CASE WHEN sa.selected_option = 'c' THEN 1 ELSE 0 END) AS c_count,
            SUM(CASE WHEN sa.selected_option = 'd' THEN 1 ELSE 0 END) AS d_count,
            SUM(CASE WHEN sa.selected_option = q.correct_option THEN 1 ELSE 0 END) AS correct_count
        FROM student_answers sa
        JOIN questions q ON q.id = sa.question_no
        WHERE sa.exam_id = ?
        GROUP BY sa.question_no
        ORDER BY sa.question_no
    """, (exam_id,))

    analytics = cur.fetchall()
    conn.close()

    return render_template(
        "question_analytics.html",
        exam_id=exam_id,
        analytics=analytics
    )    

def calculate_cheating_risk(violations):
    score = 0

    for v in violations:
        if v["event_type"] == "TAB_SWITCH":
            score += 2
        elif v["event_type"] == "FULLSCREEN_EXIT":
            score += 3
        elif v["event_type"] == "FACE_NOT_DETECTED":
            score += 4
        else:
            score += 1

    if score >= 7:
        return "HIGH"
    elif score >= 4:
        return "MEDIUM"
    else:
        return "LOW"    


from flask import jsonify
import time

# ---------- VIOLATION ----------
from flask import request, jsonify
import sqlite3

@app.route("/exam/violation", methods=["POST"])
def exam_violation():
    # 🔁 BACKWARD COMPATIBILITY ROUTE
    # Just call the real logic
    return log_violation()
    
# ---------- TIMER ----------
# =========================
# EXAM TIMER API (STUDENT)
# =========================

@app.route("/admin/exam/<int:exam_id>/violations")
def admin_exam_violations(exam_id):
    if not session.get("admin"):
        return jsonify([])

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            s.roll,
            s.name,
            v.event_type,
            COUNT(*) as cnt,
            MAX(v.created_at) as last_time
        FROM exam_violations v
        JOIN students s ON s.id = v.student_id
        WHERE v.exam_id=?
        GROUP BY v.student_id, v.event_type
        ORDER BY last_time DESC
    """, (exam_id,))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route("/exam/pause", methods=["POST"])
def exam_pause():

    data = request.get_json(force=True)
    student_id = data["student_id"]
    exam_id = data["exam_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exam_sessions
        SET status='PAUSED'
        WHERE student_id=? AND exam_id=?
    """, (student_id, exam_id))

    conn.commit()
    conn.close()
    return {"paused": True}

@app.route("/exam/pause", methods=["POST"])
def exam_pause_api():
    data = request.get_json()
    student_id = data.get("student_id")
    exam_id = data.get("exam_id")

    result = pause_exam(student_id, exam_id)
    return jsonify(result)
@app.route("/admin/exam/<int:exam_id>/start", methods=["POST"])
def admin_start_exam(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1️⃣ Mark exam started
    cur.execute("""
        UPDATE exams
        SET started = 1
        WHERE id = ?
    """, (exam_id,))

    # 2️⃣ FORCE all APPROVED students → RUNNING
    import time
    now = int(time.time())

    cur.execute("""
    UPDATE exam_sessions
    SET
     status = 'RUNNING',
     paused = 0,
     paused_at = NULL,

     timer_enabled = 1,

     -- ✅ FIX: take duration from exams table
     exam_duration = (
     SELECT timer_minutes * 60
     FROM exams
     WHERE id = ?
     ),

     timer_started_at = COALESCE(timer_started_at, ?)
    WHERE exam_id = ?
    """, (exam_id, now, exam_id))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")

@app.route("/admin/student/<int:student_id>/approve", methods=["POST"])
def admin_approve_student(student_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1️⃣ Get exam_id of student
    cur.execute("""
        SELECT exam_id
        FROM students
        WHERE id = ?
    """, (student_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return redirect(request.referrer)

    exam_id = row["exam_id"]

    # 2️⃣ Mark student approved
    cur.execute("""
        UPDATE students
        SET status = 'approved'
        WHERE id = ?
    """, (student_id,))

    # 3️⃣ CREATE or UPDATE exam_session → APPROVED
    cur.execute("""
        SELECT id FROM exam_sessions
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE exam_sessions
            SET status = 'APPROVED'
            WHERE student_id = ? AND exam_id = ?
        """, (student_id, exam_id))
    else:
        cur.execute("""
            INSERT INTO exam_sessions (student_id, exam_id, status)
            VALUES (?, ?, 'APPROVED')
        """, (student_id, exam_id))

    conn.commit()
    conn.close()

    return redirect(request.referrer)

@app.route("/student/waiting/status/<int:exam_id>")
def student_waiting_status(exam_id):

    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"status": "NOT_LOGGED_IN"})

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1️⃣ Exam started?
    cur.execute("SELECT started FROM exams WHERE id = ?", (exam_id,))
    exam = cur.fetchone()

    # 2️⃣ Student exam session
    cur.execute("""
        SELECT status
        FROM exam_sessions
        WHERE exam_id = ? AND student_id = ?
    """, (exam_id, student_id))
    session_row = cur.fetchone()

    conn.close()

    # 🔥 FINAL CORRECT LOGIC

    # Exam running → GO TO EXAM
    if session_row and session_row["status"] == "RUNNING":
        return jsonify({"status": "RUNNING"})

    # Student approved → WAIT FOR START
    if session_row and session_row["status"] == "APPROVED":
        return jsonify({"status": "APPROVED"})

    # Default
    return jsonify({"status": "WAITING"})

@app.route("/exam-paused")
def exam_paused_page():
    if not session.get("student_id"):
        return redirect("/student/login")

    return render_template("student/exam_paused.html")

from datetime import datetime

answered_at = datetime.now()
time_taken = 0

@app.route("/student/save-answer", methods=["POST"])
def save_answer():
    data = request.get_json()

    # ✅ EXISTING (DO NOT CHANGE)
    exam_id = session.get("exam_id")
    student_id = session.get("student_id")
    question_no = data.get("question_no")
    selected_option = data.get("selected_option")

    # ✅ NEW (ONLY ADD)
    time_taken = data.get("time_taken", 0)

    if not student_id or not exam_id:
        return jsonify({"error": "session missing"}), 401

    conn = sqlite3.connect("database_v2.db")
    cur = conn.cursor()

    # ✅ SAME QUERY + ONLY ONE COLUMN ADDED
    cur.execute("""
        INSERT INTO student_answers
            (exam_id, student_id, question_no, selected_option, time_taken)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(exam_id, student_id, question_no)
        DO UPDATE SET
            selected_option = excluded.selected_option,
            time_taken = excluded.time_taken
    """, (
        exam_id,
        student_id,
        question_no,
        selected_option,
        time_taken
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "saved",
        "time_taken": time_taken
    })


def student_pause_check(exam_id):
    import sqlite3
    conn = sqlite3.connect("database_v2.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # existing code below (DO NOT CHANGE)
    cur.execute("""
        SELECT paused
        FROM exam_sessions
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))

    row = cur.fetchone()

    return {
        "paused": row["paused"] if row else 0
    }


@app.route("/admin/pause/<int:exam_id>/<int:student_id>", methods=["GET,POST"])
def admin_pause_exam(exam_id, student_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
      UPDATE exam_sessions
      SET status = 'PAUSED',
       paused = 1,
       resume_allowed = 0
     WHERE exam_id = ? AND student_id = ?
    """, (exam_id, student_id))
    conn.commit()
    return "Paused"

@app.route("/system/auto-pause/<int:exam_id>/<int:student_id>")
def system_auto_pause(exam_id, student_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT status FROM exam_student_status
        WHERE exam_id=? AND student_id=?
    """, (exam_id, student_id))

    row = cur.fetchone()
    conn.close()

    if row and row["status"] == "PAUSED":
        return jsonify({"paused": 1})

    # ✅ VERY IMPORTANT
    return jsonify({"paused": 0})

@app.route("/exam-paused")
def exam_paused():
    exam_id = session.get("exam_id")
    if not exam_id:
        return redirect("/student/login")

    return render_template(
        "student/exam_paused.html",
        exam_id=exam_id   # ✅ THIS WAS MISSING
    )





import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database_v2.db")

@app.route("/student/log-violation", methods=["POST"])
def log_violation():
    print("🔥 STUDENT LOG VIOLATION HIT:", request.json)
    data = request.get_json()
    exam_id = session["exam_id"]
    student_id = session["student_id"]
    event_type = data.get("event_type")
    # 👁️ If no face detected → save face snapshot
    if event_type == "no_face":
        save_face_snapshot_internal(student_id, exam_id)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1️⃣ Log violation
    cur.execute("""
        INSERT INTO exam_violations (student_id, exam_id, event_type)
        VALUES (?, ?, ?)
    """, (student_id, exam_id, event_type))

    # 2️⃣ Count violations
    cur.execute("""
        SELECT COUNT(*) 
        FROM exam_violations
        WHERE exam_id = ? AND student_id = ?
    """, (exam_id, student_id))

    violation_count = cur.fetchone()[0]
    print("🔥 VIOLATION COUNT:",violation_count)

    response = {"count": violation_count}

    # 3️⃣ Warnings (2–5)
    if 2 <= violation_count <= 5:
        response["warning"] = 1

    # 4️⃣ AUTO PAUSE (6th)
    if violation_count >= 6:
        cur.execute("""
            UPDATE exam_sessions
            SET status = 'PAUSED',
                paused = 1,
                resume_allowed = 0
            WHERE exam_id = ? AND student_id = ?
        """, (exam_id, student_id))

        response["paused"] = 1

    conn.commit()
    conn.close()

    return jsonify(response)


@app.route("/student/exam/resume-status")
def resume_status():
    student_id = session.get("student_id")
    exam_id = session.get("exam_id")

    if not student_id or not exam_id:
        return jsonify({"resumed": 0})

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT status
        FROM exam_sessions
        WHERE exam_id = ? AND student_id = ?
    """, (exam_id, student_id))

    row = cur.fetchone()
    conn.close()

    if row and row[0] == "RUNNING":
        return jsonify({
            "resumed": 1,
            "exam_id": exam_id   # 🔥 VERY IMPORTANT
        })

    return jsonify({"resumed": 0})



@app.route("/student/exam/resume-status")
def student_resume_status():
    student_id = session.get("student_id")
    exam_id = session.get("exam_id")

    if not student_id or not exam_id:
        return jsonify({"resumed": 0})

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT status
        FROM exam_sessions
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))

    row = cur.fetchone()
    conn.close()

    if row and row["status"] == "RUNNING":
        return jsonify({"resumed": 1})

    return jsonify({"resumed": 0})
@app.route("/admin/exam/<int:exam_id>/resume/<int:student_id>", methods=["POST"])
def admin_resume_exam(exam_id, student_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exam_sessions
        SET
            paused = 0,
            resume_allowed = 1,
            status = 'RUNNING',
            paused_at = NULL
        WHERE exam_id = ? AND student_id = ?
    """, (exam_id, student_id))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/analytics")

@app.route("/student/exam/resume-status")
def student_exam_resume_status():
    student_id = session.get("student_id")
    exam_id = session.get("exam_id")  # ensure you set this on exam start

    if not student_id or not exam_id:
        return jsonify({"resume": False})

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT paused, status
        FROM exam_sessions
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))

    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"resume": False})

    # 🔥 FINAL DECISION
    if row["paused"] == 0 and row["status"] == "RUNNING":
        return jsonify({"resume": True})

    return jsonify({"resume": False})  

@app.route("/student/exam/auto-pause", methods=["POST"])
def auto_pause_exam():
    student_id = session.get("student_id")
    exam_id = session.get("exam_id")

    if not student_id or not exam_id:
        return jsonify({"success": False})

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exam_sessions
        SET status = 'PAUSED',
            paused = 1,
            resume_allowed = 0,
            paused_at = CURRENT_TIMESTAMP
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

from datetime import datetime
import sqlite3

from datetime import datetime

@app.route("/student/exam-timer")
def student_exam_timer():

    student_id = session.get("student_id")
    exam_id = session.get("exam_id")

    if not student_id or not exam_id:
        return jsonify({"enabled": False})

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            timer_enabled,
            timer_started_at,
            exam_duration
        FROM exam_sessions
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))

    row = cur.fetchone()
    conn.close()

    if not row or not row["timer_enabled"]:
        return jsonify({"enabled": False})

    start_raw = row["timer_started_at"]

    if not start_raw:
        return jsonify({"enabled": False})

    # INTEGER unix timestamp
    if isinstance(start_raw, int):
        start = datetime.fromtimestamp(start_raw)
    else:
        # STRING timestamp
        start = datetime.fromisoformat(start_raw)

    elapsed = (datetime.now() - start).total_seconds()
    remaining = max(0, int(row["exam_duration"]) - int(elapsed))

    return jsonify({
        "enabled": True,
        "remaining_seconds": remaining
    })
@app.route("/student/start-exam-timer", methods=["POST"])
def start_exam_timer():
    if "student_id" not in session or "exam_id" not in session:
        return {"error": "unauthorized"}, 401

    student_id = session["student_id"]
    exam_id = session["exam_id"]

    db = get_db()

    # check if start_time already exists
    row = db.execute("""
        SELECT start_time FROM exam_sessions
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id)).fetchone()

    if row and row["start_time"]:
        # already started — do nothing
        return {"started": True}

    now = int(time.time())

    db.execute("""
        UPDATE exam_sessions
        SET start_time = ?
        WHERE student_id = ? AND exam_id = ?
    """, (now, student_id, exam_id))

    db.commit()

    return {"started": True}

@app.route("/admin/exam/<int:exam_id>/pause/<int:student_id>")
def pause_exam(exam_id, student_id):
    conn = get_db()
    cur = conn.cursor()

    import time

    cur.execute("""
        UPDATE exam_sessions
        SET
            status = 'PAUSED',
            paused = 1,
            paused_at = ?
        WHERE exam_id = ? AND student_id = ?
    """, (int(time.time()), exam_id, student_id))

    conn.commit()
    conn.close()

    return jsonify({"paused": 1})


    

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)