import pdfplumber

def extract_full_pdf_text(pdf_file):
    full_text = ""

    with pdfplumber.open(pdf_file) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):

            # 🔥 WORD-LEVEL EXTRACTION
            words = page.extract_words(
                use_text_flow=True,
                keep_blank_chars=False
            )

            if not words:
                print(f"⚠️ Page {page_no} empty")
                continue

            line = ""
            prev_top = None

            for w in words:
                top = round(w["top"])

                if prev_top is None or abs(top - prev_top) <= 3:
                    line += w["text"] + " "
                else:
                    full_text += line.strip() + "\n"
                    line = w["text"] + " "

                prev_top = top

            if line.strip():
                full_text += line.strip() + "\n"

            full_text += "\n"  # page gap

    return full_text