from PIL import Image
import pytesseract

# ⚠️ Tesseract path (Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

img = Image.open("test_mcq.jpg")

text = pytesseract.image_to_string(img)

print(text)
from ocr_to_mcq import parse_mcq_text

mcqs = parse_mcq_text(text)

print("\n--- PARSED MCQs ---\n")
for m in mcqs:
    print(m["question"])
    for opt in m["options"]:
        print(opt)
    print()

from database import save_mcqs

save_mcqs(mcqs)
print("✅ MCQs saved to database")    