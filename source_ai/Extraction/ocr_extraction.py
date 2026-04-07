import os
import cv2
from PIL import Image
import pytesseract
import torch

# ==============================
#  PATHS 
# ==============================
printed_folder = r"F:\Printed_Images"
output_folder = r"F:\ocr_output"

os.makedirs(output_folder, exist_ok=True)
printed_ocr_output = os.path.join(output_folder, "printed")

os.makedirs(printed_ocr_output, exist_ok=True)

# ==============================
#  TESSERACT SETUP
# ==============================
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ==============================
#  PRINTED OCR (TESSERACT)
# ==============================
def ocr_printed(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return ""

    text = pytesseract.image_to_string(img, config="--oem 3 --psm 6")
    return text

# ==============================
#  SAVE OUTPUT
# ==============================
def save_text(folder, filename, text):
    out_path = os.path.join(folder, filename + ".txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

# ==============================
#  PROCESS PRINTED DATASET
# ==============================
print(" Processing Printed Invoices...")

count = 0

for root, dirs, files in os.walk(printed_folder):
    for file in files:
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):

            name = os.path.splitext(file)[0]
            out_file = os.path.join(printed_ocr_output, name + ".txt")

            #  Skip already processed
            if os.path.exists(out_file):
                continue

            path = os.path.join(root, file)
            text = ocr_printed(path)

            save_text(printed_ocr_output, name, text)

            count += 1
            print(f"Printed Processed: {count}")

print(" Printed OCR Done!")
