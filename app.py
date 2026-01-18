import re
import time
import os
import sqlite3
import pdfplumber

from flask import (
    Flask,
    request,
    redirect,
    render_template,
    session,
    send_from_directory
)

# --------------------------------
# ONLY for init & migration
# --------------------------------
from db import  migrate_questions_table

# --------------------------------
# Runtime DB usage (students, inserts, locks)
# --------------------------------
from database import get_db, insert_student, _db_lock


# --------------------------------
# APP INIT
# --------------------------------
app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret")


# --------------------------------
# APP START (RUN ONCE)
# --------------------------------
with app.app_context():
    migrate_questions_table()


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



@app.route("/")
def splash():
    return render_template("splash.html")

@app.route("/login")
def index():
    return render_template("index.html")

# -------------------------------------------------
# ADMIN LOGIN
# -------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin":
            session["admin"] = True
            return redirect("/admin-dashboard")
    return render_template("admin_login.html")

# -------------------------------------------------
# ADMIN DASHBOARD
# -------------------------------------------------
@app.route("/admin-dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect("/admin/login")
    return render_template("admin_dashboard.html")

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

@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        roll = request.form.get("roll", "").strip()
        name = request.form.get("name", "").strip()
        exam_id_raw = request.form.get("exam_id", "").strip()

        # -----------------------------
        # 1️⃣ BASIC VALIDATION
        # -----------------------------
        if not roll or not name or not exam_id_raw.isdigit():
            return render_template(
                "student/student_login.html",
                error="❌ Please enter valid details"
            )

        exam_id = int(exam_id_raw)

        conn = get_db()
        cur = conn.cursor()

        # -----------------------------
        # 2️⃣ CHECK EXAM EXISTS
        # -----------------------------
        cur.execute("SELECT started FROM exams WHERE id = ?", (exam_id,))
        exam = cur.fetchone()

        if not exam:
            conn.close()
            return render_template(
                "student/student_login.html",
                error="❌ Invalid Exam ID"
            )

        started = exam["started"]  # 0 or 1

        # -----------------------------
        # 3️⃣ CHECK EXISTING STUDENT
        # -----------------------------
        cur.execute("""
            SELECT status
            FROM students
            WHERE roll = ? AND exam_id = ? AND removed = 0
        """, (roll, exam_id))
        existing = cur.fetchone()

        # -----------------------------
        # 4️⃣ DECIDE STATUS (IMPORTANT)
        # -----------------------------
        # 👉 ALWAYS require admin approval
        # - before exam
        # - during exam
        status = "pending"

        if existing:
            cur.execute("""
                UPDATE students
                SET status = ?, removed = 0
                WHERE roll = ? AND exam_id = ?
            """, (status, roll, exam_id))
        else:
            cur.execute("""
                INSERT INTO students (exam_id, roll, name, status, removed)
                VALUES (?, ?, ?, ?, 0)
            """, (exam_id, roll, name, status))

        conn.commit()
        conn.close()

        # -----------------------------
        # 5️⃣ SESSION (ONE FORMAT ONLY)
        # -----------------------------
        session["student"] = {
            "roll": roll,
            "name": name
        }
        session["exam_id"] = exam_id

        # -----------------------------
        # 6️⃣ ALWAYS GO TO WAITING ROOM
        # -----------------------------
        return redirect("/student/waiting")

    # -----------------------------
    # GET REQUEST
    # -----------------------------
    return render_template("student/student_login.html")

# -------------------------------------------------
# START EXAM
# -------------------------------------------------
@app.route("/admin/exam/<int:exam_id>/start", methods=["POST"])
def start_exam(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exams
        SET started = 1
        WHERE id = ?
    """, (exam_id,))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")

# -------------------------------------------------
# STUDENT LOGIN
# -------------------------------------------------


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

# -------------------------------------------------
# STUDENT WAITING
# -------------------------------------------------
from flask import render_template, session, redirect


  # ------------------------------------------
# STUDENT WAITING ROOM (SAFE VERSION)
# ------------------------------------------

@app.route("/student/submitted")
def student_submitted():
    return render_template("student/student_submitted.html")



@app.route("/student/waiting")
def student_waiting():

    if "student" not in session or "exam_id" not in session:
        return redirect("/student/login")

    student = session["student"]
    exam_id = session["exam_id"]

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT status
        FROM students
        WHERE roll = ? AND exam_id = ?
    """, (student["roll"], exam_id))
    row = cur.fetchone()

    cur.execute("""
        SELECT started
        FROM exams
        WHERE id = ?
    """, (exam_id,))
    exam = cur.fetchone()

    conn.close()

    status = row["status"] if row else "pending"
    started = exam["started"] if exam else 0

    # ✅ ONLY THIS CONDITION
    if status == "approved" and started == 1:
        return redirect(f"/student/exam/{exam_id}")

    return render_template(
        "student/student_waiting.html",
        student=student,
        status=status
    )


@app.route("/admin/exam/<int:exam_id>/release_results", methods=["POST"])
def release_results(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exams
        SET results_released = 1
        WHERE id = ?
    """, (exam_id,))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")

@app.route("/student/check-results_status")
def check_results_status():

    if "exam_id" not in session:
        return {"released": False}

    exam_id = session["exam_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT results_released
        FROM exams
        WHERE id = ?
    """, (exam_id,))
    row = cur.fetchone()

    conn.close()

    return {
        "released": bool(row and row["results_released"] == 1)
    } 


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
    if "student" not in session:
        return redirect("/student/login")

    roll = session["student"]["roll"]
    exam_id = session["exam_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE students
        SET status = 'left'
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))
    conn.commit()
    conn.close()

    session.clear()
    return redirect("/")    

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
    if "student" not in session:
        return {"status": "logout"}

    roll = session["student"]["roll"]
    exam_id = session["exam_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT status FROM students
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))
    row = cur.fetchone()

    conn.close()

    if not row:
        return {"status": "removed"}

    return {"status": row["status"]}

# -------------------------------------------------
# STUDENT SUBMIT
# -------------------------------------------------


@app.route("/student/submit_exam", methods=["POST"])
def submit_exam():
    exam_id = int(request.form.get("exam_id"))
    student = session.get("student")
    roll = student["roll"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT question_no
        FROM questions
        WHERE exam_id = ?
    """, (exam_id,))
    questions = cur.fetchall()

    for q in questions:
        q_no = q["question_no"]
        selected = request.form.get(f"answer_{q_no}")

        if selected:
            cur.execute("""
                INSERT INTO student_answers
                (student_id, exam_id, question_no, selected_option)
                VALUES (?, ?, ?, ?)
            """, (roll, exam_id, q_no, selected))

    conn.commit()
    conn.close()

    return redirect("/student/wait-for-results")


@app.route("/student/wait-for-results")
def student_wait_for_results():
    if "student" not in session:
        return redirect("/student/login")

    return render_template("student/wait_for_results.html")


@app.route("/student/wait-for-results")
def wait_for_results():

    if "student" not in session or "exam_id" not in session:
        return redirect("/student/login")

    return render_template("student/student_wait_for_results.html")   

from evaluator import evaluate_exam


@app.route("/student/done")
def student_done():

    if not session.get("student"):
        return redirect("/")

    # ✅ get student_id properly
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM students
        WHERE roll = ? AND exam_id = ?
    """, (session["student"]["roll"], session["exam_id"]))
    row = cur.fetchone()
    conn.close()

    if not row:
        return "Student not found", 400

    student_id = row["id"]
    exam_id = session["exam_id"]

    # ✅ NOW evaluate
    result = evaluate_exam(student_id, exam_id)

    return render_template("student/student_done.html", result=result)


@app.route("/admin/student/<int:exam_id>/<roll>/approve", methods=["POST"])
def approve_student(exam_id, roll):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE students
        SET status = 'approved'
        WHERE exam_id = ? AND roll = ?
    """, (exam_id, roll))
    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")

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


@app.route("/admin/exam/<int:exam_id>/resume/<int:student_id>", methods=["POST"])
def admin_resume_student(exam_id, student_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE students
        SET status = 'approved'
        WHERE id = ? AND exam_id = ?
    """, (student_id, exam_id))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")

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

@app.route("/exam/resume", methods=["POST"])
def exam_resume():
    student_id = request.json["student_id"]
    exam_id = request.json["exam_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exam_sessions
        SET status='RUNNING'
        WHERE student_id=? AND exam_id=?
    """, (student_id, exam_id))

    conn.commit()
    conn.close()

    return {"ok": True}


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

@app.route("/exam/pause", methods=["POST"])
def exam_pause():
    data = request.get_json(force=True)
    student_id = data.get("student_id")
    exam_id = data.get("exam_id")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT status FROM exam_sessions
        WHERE student_id=? AND exam_id=?
    """, (student_id, exam_id))
    row = cur.fetchone()

    if not row or row[0] == "SUBMITTED":
        conn.close()
        return jsonify({"status": "IGNORED"})

    cur.execute("""
        UPDATE exam_sessions
        SET status='PAUSED'
        WHERE student_id=? AND exam_id=?
    """, (student_id, exam_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "PAUSED"})

# -------------------------------------------------
# ADMIN EXAM CONTROL
# -------------------------------------------------    

@app.route("/admin/exam/<int:exam_id>/control")
def admin_exam_control(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -------------------------------------------------
    # ✅ STEP 2 — AUTO PAUSE (TAB SWITCH / NO PING)
    # -------------------------------------------------
    cur.execute("""
        SELECT id, last_ping, status
        FROM exam_sessions
        WHERE exam_id = ?
    """, (exam_id,))

    sessions = cur.fetchall()
    now = int(time.time())

    for s in sessions:
        if s["status"] == "RUNNING" and s["last_ping"]:
            try:
                if now - int(s["last_ping"]) > 10:
                    cur.execute("""
                        UPDATE exam_sessions
                        SET status = 'PAUSED'
                        WHERE id = ?
                    """, (s["id"],))
            except:
                pass

    conn.commit()

    # -------------------------------------------------
    # ✅ EXISTING STUDENT FETCH (UNCHANGED)
    # -------------------------------------------------
    cur.execute("""
        SELECT
            s.id as student_id,
            s.roll,
            s.name,
            s.status AS student_status,
            COALESCE(es.status, 'NOT_STARTED') AS exam_status
        FROM students s
        LEFT JOIN exam_sessions es
            ON es.student_id = s.id AND es.exam_id = ?
        WHERE s.exam_id = ?
    """, (exam_id, exam_id))

    students = cur.fetchall()
    conn.close()

    return render_template(
        "exam_control.html",
        students=students,
        exam_id=exam_id
    )


@app.route("/admin/exam/<int:exam_id>/resume/<roll>", methods=["POST"])
def admin_resume_exam(exam_id, roll):

    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    # get student id
    cur.execute("""
        SELECT id
        FROM students
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return "Student not found", 404

    student_id = row[0]

    # ✅ VERY IMPORTANT
    cur.execute("""
        UPDATE exam_sessions
        SET status = 'RUNNING'
        WHERE student_id = ? AND exam_id = ?
    """, (student_id, exam_id))

    conn.commit()
    conn.close()

    print("✅ ADMIN RESUMED EXAM:", student_id, exam_id)

    return redirect(f"/admin/exam/{exam_id}/control")

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




from datetime import datetime




@app.route('/student/exam/<int:exam_id>', methods=['GET', 'POST'])
def student_exam(exam_id):

    student = session.get("student")
    if not student:
        return redirect("/student/login")

    roll = student["roll"]

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---------------- STUDENT ----------------
    cur.execute("""
        SELECT id, status, removed
        FROM students
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))
    student_row = cur.fetchone()

    if not student_row:
        conn.close()
        return redirect("/student/login")

    student_id = student_row["id"]

    if student_row["removed"] == 1:
        conn.close()
        return redirect("/student/login")

    if student_row["status"] == "submitted":
        conn.close()
        return redirect("/student/result")

    if student_row["status"] != "approved":
        conn.close()
        return render_template("student/exam_paused.html", exam_id=exam_id)

    # ======================================================
    # ✅ FIX-2: SESSION STATUS CHECK (BEFORE EXAM PAGE LOAD)
    # ======================================================
    cur.execute("""
        SELECT status
        FROM exam_sessions
        WHERE student_id=? AND exam_id=?
    """, (student_id, exam_id))
    session_check = cur.fetchone()

    if session_check:
        if session_check["status"] == "PAUSED":
            conn.close()
            return render_template("student/exam_paused.html", exam_id=exam_id)

        if session_check["status"] == "REMOVED":
            conn.close()
            return redirect("/student/login")

        if session_check["status"] == "SUBMITTED":
            conn.close()
            return redirect("/student/result")
    # ======================================================

    # ---------------- EXAM INFO ----------------
    cur.execute("""
        SELECT started, enable_timer, timer_minutes
        FROM exams
        WHERE id = ?
    """, (exam_id,))
    exam_row = cur.fetchone()

    if not exam_row or exam_row["started"] != 1:
        conn.close()
        return redirect("/student/wait-for-results")

    enable_timer = exam_row["enable_timer"] or 0
    duration_minutes = exam_row["timer_minutes"] or 0

    # ---------------- EXAM SESSION CREATE (ONLY ONCE) ----------------
    if not session_check:
        cur.execute("""
            INSERT INTO exam_sessions (
                student_id, exam_id, status,
                timer_enabled, timer_minutes, timer_started_at
            )
            VALUES (?, ?, 'RUNNING', ?, ?, ?)
        """, (
            student_id,
            exam_id,
            enable_timer,
            duration_minutes,
            datetime.utcnow().isoformat() if enable_timer else None
        ))
        conn.commit()

    # ---------------- SUBMIT ----------------
    if request.method == "POST":
        correct = 0

        cur.execute("""
            SELECT id, correct_option
            FROM questions
            WHERE exam_id=?
        """, (exam_id,))
        qs = cur.fetchall()

        for q in qs:
            ans = request.form.get(f"q_{q['id']}")
            if ans and q["correct_option"] and ans.upper() == q["correct_option"].upper():
                correct += 1

        total = len(qs)

        cur.execute("DELETE FROM results WHERE student_id=? AND exam_id=?", (student_id, exam_id))
        cur.execute("""
            INSERT INTO results (student_id, exam_id, correct, total)
            VALUES (?, ?, ?, ?)
        """, (student_id, exam_id, correct, total))

        cur.execute("UPDATE students SET status='submitted' WHERE id=?", (student_id,))
        cur.execute("""
            UPDATE exam_sessions
            SET status='SUBMITTED'
            WHERE student_id=? AND exam_id=?
        """, (student_id, exam_id))

        conn.commit()
        conn.close()
        return redirect("/student/result")

    # ---------------- QUESTIONS ----------------
    cur.execute("""
        SELECT id, question, option_a, option_b, option_c, option_d
        FROM questions
        WHERE exam_id=?
        ORDER BY question_no
    """, (exam_id,))
    questions = cur.fetchall()

    conn.close()

    return render_template(
        "student/student_exam.html",
        questions=questions,
        exam_id=exam_id,
        student_id=student_id,
        enable_timer=enable_timer,
        duration_minutes=duration_minutes
    )


@app.route("/admin/exam/<int:exam_id>/resume/<int:student_id>", methods=["POST"])
def admin_exam_resume(exam_id, student_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exam_sessions
        SET status = 'RUNNING',
            resumed_at = strftime('%s','now')
        WHERE exam_id = ? AND student_id = ?
    """, (exam_id, student_id))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")


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

@app.route("/exam/timer/<int:exam_id>")
def exam_timer(exam_id):

    student = session.get("student")
    if not student:
        return {"enabled": False}

    roll = student["roll"]

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---------------- STUDENT ----------------
    cur.execute("""
        SELECT id
        FROM students
        WHERE roll=? AND exam_id=?
    """, (roll, exam_id))
    s = cur.fetchone()

    if not s:
        conn.close()
        return {"enabled": False}

    student_id = s["id"]

    # ---------------- SESSION ----------------
    cur.execute("""
        SELECT
            timer_started_at,
            total_paused_seconds,
            timer_enabled,
            timer_minutes,
            status
        FROM exam_sessions
        WHERE student_id=? AND exam_id=?
    """, (student_id, exam_id))
    sess = cur.fetchone()
    conn.close()

    if not sess:
        return {"enabled": False}

    if sess["timer_enabled"] != 1:
        return {"enabled": False}

    if not sess["timer_started_at"]:
        return {"enabled": False}

    if sess["status"] == "SUBMITTED":
        return {"enabled": False}

    # ---------------- TIMER CALC ----------------
    started_at = datetime.fromisoformat(sess["timer_started_at"])
    paused_seconds = sess["total_paused_seconds"] or 0
    total_seconds = sess["timer_minutes"] * 60

    elapsed = (datetime.utcnow() - started_at).total_seconds()
    effective_elapsed = elapsed - paused_seconds

    remaining = max(0, int(total_seconds - effective_elapsed))

    return {
        "enabled": True,
        "remaining_seconds": remaining,
        "status": sess["status"]   # 🔥 VERY IMPORTANT
    }

# -------------------------------------------------
# RUN
# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)