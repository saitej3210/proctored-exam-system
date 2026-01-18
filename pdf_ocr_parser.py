import pytesseract
from pdf2image import convert_from_path
import cv2
import numpy as np

# CHANGE PATH IF NEEDED
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text_from_scanned_pdf(pdf_path):
    text = ""

    images = convert_from_path(pdf_path, dpi=300)

    for img in images:
        open_cv_img = np.array(img)
        gray = cv2.cvtColor(open_cv_img, cv2.COLOR_BGR2GRAY)
        ocr_text = pytesseract.image_to_string(gray)
        text += ocr_text + "\n"

    return text