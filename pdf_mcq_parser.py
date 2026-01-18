import re
import pdfplumber

def parse_mcq_pdf(pdf_path):
    questions = []

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    q_pattern = re.compile(r'^(Q\d+\.|\d+\.)\s*(.*)', re.IGNORECASE)
    opt_pattern = re.compile(r'^([A-Da-d1-4])[).]\s*(.*)')

    current_q = None

    for line in lines:
        q_match = q_pattern.match(line)
        opt_match = opt_pattern.match(line)

        if q_match:
            if current_q:
                questions.append(current_q)

            current_q = {
                "question": q_match.group(2),
                "A": "",
                "B": "",
                "C": "",
                "D": ""
            }

        elif opt_match and current_q:
            key = opt_match.group(1).upper()

            # Normalize numeric options → A/B/C/D
            if key == "1": key = "A"
            elif key == "2": key = "B"
            elif key == "3": key = "C"
            elif key == "4": key = "D"

            current_q[key] = opt_match.group(2)

    if current_q:
        questions.append(current_q)

    return questions