import re

def parse_mcq_text(text):
    questions = []

    blocks = re.split(r'\n(?=Q\d+[\.\)])', text)

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]

        if len(lines) < 5:
            continue

        question_line = lines[0]
        options = lines[1:5]

        if len(options) < 4:
            continue

        questions.append({
            "question": question_line,
            "a": options[0],
            "b": options[1],
            "c": options[2],
            "d": options[3]
        })

    return questions