import re
from pdfminer.high_level import extract_text

def parse_answer_key(pdf_path):
    text = extract_text(pdf_path)
    answers = {}

    for line in text.splitlines():
        line = line.strip()

        # Supports:
        # 1) a
        # 1) A
        # Q1. a
        # Q1. A
        match = re.match(
            r"(?:Q)?\s*(\d+)\s*[.)]\s*([A-Da-d])",
            line
        )

        if match:
            qno = int(match.group(1))
            ans = match.group(2).upper()
            answers[qno] = ans

    return answers