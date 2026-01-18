def parse_mcq_text(text):
    questions = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    q = None
    options = []

    for line in lines:
        if line[0].isdigit() and "." in line:
            if q:
                questions.append({
                    "question": q,
                    "options": options
                })
            q = line
            options = []
        elif line.startswith(("a)", "b)", "c)", "d)")):
            options.append(line)

    if q:
        questions.append({
            "question": q,
            "options": options
        })

    return questions