import os
import sqlite3
import re
import pdfplumber
from flask import (
    Flask,
    request,
    redirect,
    render_template,
    session,
    send_from_directory
)

from database import get_db, insert_student, _db_lock


# -------------------------------------------------
# APP INIT
# -------------------------------------------------
app = Flask(__name__, template_folder="templates")
app.secret_key = "secret123"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------------------------------------
# DB INIT
# -------------------------------------------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            roll TEXT,
            name TEXT,
            status TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            question TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct_option TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            roll TEXT,
            question_id INTEGER,
            selected_option TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------------------------------
# HOME (OLD UI)
# -------------------------------------------------
@app.route("/")
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
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO exams (started) VALUES (0)")
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
        # ✅ MUST be inside POST
        qpdf = request.files.get("question_pdf")
        apdf = request.files.get("answer_pdf")

        if not qpdf:
            return "Question PDF missing", 400

        # ✅ save question pdf
        qpath = os.path.join(UPLOAD_FOLDER, f"exam_{exam_id}_questions.pdf")
        qpdf.save(qpath)

        # ✅ save answer pdf (optional)
        if apdf:
            apath = os.path.join(UPLOAD_FOLDER, f"exam_{exam_id}_answers.pdf")
            apdf.save(apath)

        # ✅ parse AFTER save
        parsed_questions = parse_mcq_pdf(qpath)

        if not parsed_questions:
            return "No questions detected in PDF", 400

        conn = get_db()
        cur = conn.cursor()

        for q in parsed_questions:

            # 🛡️ SAFETY CHECK – skip broken questions
            required_keys = ["question", "A", "B", "C", "D"]
            if not all(k in q and q[k] for k in required_keys):
                print("⚠️ Skipping invalid question:", q)
                continue

            cur.execute("""
                INSERT INTO questions
                (exam_id, question, option_a, option_b, option_c, option_d)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                exam_id,
                q["question"],
                q.get("A", ""),
                q.get("B", ""),
                q.get("C", ""),
                q.get("D", "")
            ))

        conn.commit()
        conn.close()

        return redirect(f"/admin/exam/{exam_id}/control")

    # 👇 GET request ONLY shows page
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


# -------------------------------------------------
# ADMIN EXAM CONTROL
# -------------------------------------------------
@app.route("/admin/exam/<int:exam_id>/control")
def admin_exam_control(exam_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT roll, name, status, last_ping
        FROM students
        WHERE exam_id = ?
    """, (exam_id,))
    rows = cur.fetchall()
    conn.close()

    students = [dict(r) for r in rows]

    # 🔥 STEP 4 — HERE
    import time
    now = int(time.time())

    for s in students:
        if s.get("last_ping") and s["status"] == "in_exam":
            if now - int(s["last_ping"]) > 15:
                s["status"] = "left_exam"

                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE students
                    SET status = 'left_exam'
                    WHERE exam_id = ? AND roll = ?
                """, (exam_id, s["roll"]))
                conn.commit()
                conn.close()

    return render_template(
        "exam_control.html",
        monitoring=students,
        exam_id=exam_id
    )





# -------------------------------------------------
# START EXAM
# -------------------------------------------------
@app.route("/admin/exam/<int:exam_id>/start", methods=["POST"])
def start_exam(exam_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE exams SET started = 1 WHERE id = ?", (exam_id,))
    conn.commit()
    conn.close()
    return redirect(f"/admin/exam/{exam_id}/control")

# -------------------------------------------------
# STUDENT LOGIN
# -------------------------------------------------
@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        roll = request.form["roll"]
        name = request.form["name"]

        conn = get_db()
        cur = conn.cursor()

        # latest exam
        cur.execute("SELECT id, started FROM exams ORDER BY id DESC LIMIT 1")
        exam = cur.fetchone()

        if not exam:
            return "No active exam"

        exam_id = exam["id"]
        started = exam["started"]

        # check student already exists
        cur.execute("""
            SELECT id, status FROM students
            WHERE roll = ? AND exam_id = ?
        """, (roll, exam_id))
        existing = cur.fetchone()

        if existing:
            # 🔥 IMPORTANT FIX
            if started == 1:
                # exam running → admin approval required
                cur.execute("""
                    UPDATE students
                    SET status = 'pending', removed = 0
                    WHERE roll = ? AND exam_id = ?
                """, (roll, exam_id))
            else:
                # exam not started → normal join
                cur.execute("""
                    UPDATE students
                    SET status = 'joined'
                    WHERE roll = ? AND exam_id = ?
                """, (roll, exam_id))
        else:
            # new student
            status = "pending" if started == 1 else "joined"
            cur.execute("""
                INSERT INTO students (exam_id, roll, name, status, removed)
                VALUES (?, ?, ?, ?, 0)
            """, (exam_id, roll, name, status))

        conn.commit()
        conn.close()

        session["student"] = {"roll": roll, "name": name}
        session["exam_id"] = exam_id

        return redirect("/student/waiting")

    return render_template("student/student_login.html")

# -------------------------------------------------
# STUDENT WAITING
# -------------------------------------------------
@app.route("/student/waiting")
def student_waiting():
    if "student" not in session:
        return redirect("/student/login")

    roll = session["student"]["roll"]
    exam_id = session["exam_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT status, removed
        FROM students
        WHERE roll=? AND exam_id=?
    """, (roll, exam_id))
    student = cur.fetchone()

    cur.execute("SELECT started FROM exams WHERE id=?", (exam_id,))
    exam = cur.fetchone()

    conn.close()

    if student["removed"] == 1:
        return "❌ You were removed by admin"

    # ✅ ONLY HERE student allowed into exam
    if exam["started"] == 1 and student["status"] == "joined":
        return redirect("/student/exam")

    return render_template(
        "student/student_waiting.html",
        student=session["student"],
        status=student["status"]
    )

@app.route("/student/result")
def student_result():

    if "student" not in session or "exam_id" not in session:
        return redirect("/student/login")

    exam_id = session["exam_id"]
    roll = session["student"]["roll"]

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔒 STRICT ADMIN RELEASE CHECK
    cur.execute(
        "SELECT results_released FROM exams WHERE id = ?",
        (exam_id,)
    )
    exam = cur.fetchone()

    if not exam or exam["results_released"] != 1:
        conn.close()
        return redirect("/student/wait-for-results")

    # ✅ FETCH RESULT ONLY AFTER RELEASE
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



@app.route("/admin/remove-student/<int:exam_id>/<roll>", methods=["POST"])
def remove_student(exam_id, roll):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE students
        SET removed=1
        WHERE exam_id=? AND roll=?
    """, (exam_id, roll))
    conn.commit()
    conn.close()
    return redirect(f"/admin/exam/{exam_id}/control")
# -------------------------------------------------
# STUDENT EXAM (DB QUESTIONS)
# -------------------------------------------------
@app.route("/student/exam")
def student_exam():
    if "student" not in session:
        return redirect("/student/login")

    exam_id = session["exam_id"]
    roll = session["student"]["roll"]

    conn = get_db()
    cur = conn.cursor()

    # 🔥 IMPORTANT STATUS CHECK
    cur.execute("""
        SELECT status
        FROM students
        WHERE exam_id = ? AND roll = ?
    """, (exam_id, roll))
    row = cur.fetchone()

    if not row:
        conn.close()
        return "Not allowed"

    status = row["status"]

    # ❌ ADMIN REMOVED OR LEFT
    if status in ("removed", "left_exam"):
        conn.close()
        return render_template("student/student_blocked.html")

    # ✅ ALLOWED
    cur.execute("""
        SELECT id, question, option_a, option_b, option_c, option_d
        FROM questions
        WHERE exam_id = ?
    """, (exam_id,))
    rows = cur.fetchall()
    conn.close()

    questions = [dict(r) for r in rows]

    return render_template(
        "student/student_exam.html",
        questions=questions
    )
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
    if "student" not in session:
        return "", 204

    roll = session["student"]["roll"]
    exam_id = session["exam_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE students
        SET status = 'left_exam'
        WHERE roll = ? AND exam_id = ?
    """, (roll, exam_id))
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

    if not session.get("student"):
        return redirect("/")

    # ============================
    # EXISTING CODE (DO NOT CHANGE)
    # ============================
    student_id = session.get("student_id")
    exam_id = session.get("exam_id")

    # ============================
    # ✅ ADD THIS PART (STEP 2.1)
    # ============================
    conn = get_db()
    cur = conn.cursor()

    for key, value in request.form.items():
        # expects q_1, q_2, q_3...
        if key.startswith("q_"):
            question_no = int(key.replace("q_", ""))

            cur.execute("""
                INSERT INTO student_answers
                (student_id, exam_id, question_no, selected_option)
                VALUES (?, ?, ?, ?)
            """, (student_id, exam_id, question_no, value))

    conn.commit()
    conn.close()
    # ============================
    # ✅ ADD ENDS HERE
    # ============================

    # EXISTING redirect (KEEP SAME)
    return redirect("/student/done")


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


@app.route("/admin/approve-student/<int:exam_id>/<roll>", methods=["POST"])
def approve_student(exam_id, roll):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE students
        SET status = 'joined'
        WHERE exam_id = ? AND roll = ?
    """, (exam_id, roll))

    conn.commit()
    conn.close()

    return redirect(f"/admin/exam/{exam_id}/control")    

# -------------------------------------------------
# STUDENT RESULT
# -------------------------------------------------

# -------------------------------------------------
# ADMIN RESULTS
# -------------------------------------------------
@app.route("/admin/results/<int:exam_id>")
def admin_results(exam_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    SELECT student_id, score, total
    FROM exam_results
    WHERE exam_id = ?
""", (exam_id,))
    results = cur.fetchall()
    conn.close()

    return render_template("admin_results.html", results=results)

# -------------------------------------------------
# SERVE UPLOADS
# -------------------------------------------------
@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# -------------------------------------------------
# RUN
# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)