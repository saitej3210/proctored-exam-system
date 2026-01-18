from PyPDF2 import PdfReader
import re

def parse_answer_key(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    answers = {}
    for line in text.splitlines():
        m = re.match(r"(\d+)\)\s*([a-dA-D])", line)
        if m:
            answers[int(m.group(1))] = m.group(2).lower()

    return answers