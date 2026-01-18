import re
import sqlite3

from pdf_mcq_parser import parse_mcq_pdf

def parse_question_pdf(text, exam_id):
    # wrapper function to keep old imports working
    parse_mcq_pdf(text, exam_id)

def parse_mcq_pdf(text, exam_id):
    conn = sqlite3.connect("proctored.db")
    cur = conn.cursor()

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    i = 0
    inserted = 0

    while i < len(lines):
        # Match question number
        q_match = re.match(r"^\d+\.\s*(.*)", lines[i])
        if not q_match:
            i += 1
            continue

        question = q_match.group(1)

        try:
            a = lines[i+1].split(")", 1)[1].strip()
            b = lines[i+2].split(")", 1)[1].strip()
            c = lines[i+3].split(")", 1)[1].strip()
            d = lines[i+4].split(")", 1)[1].strip()
        except:
            i += 1
            continue

        cur.execute("""
            INSERT INTO questions
            (exam_id, question_text, option_a, option_b, option_c, option_d)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (exam_id, question, a, b, c, d))

        inserted += 1
        i += 5

    conn.commit()
    conn.close()

    from pdf_mcq_parser import parse_mcq_text
from database import insert_question

from pdf_mcq_parser import parse_mcq_text
from database import insert_question

def parse_question_pdf(text, exam_id):
    questions = parse_mcq_text(text)

    print(f"DEBUG PARSED QUESTIONS = {len(questions)}")

    qno = 1
    for q in questions:
        insert_question(
            exam_id,
            qno,
            q["question"],
            q["a"],
            q["b"],
            q["c"],
            q["d"]
        )
        qno += 1

    return len(questions)

    print(f"✅ DEBUG: Questions inserted = {inserted}")