import os
import cv2
from PIL import Image
import pytesseract
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
import torch

# ==============================
#  PATHS (CHANGE THESE)
# ==============================
printed_folder = r"F:\Printed_Images"
handwritten_folder = r"F:\Handwritten_Images"
output_folder = r"F:\ocr_output"

os.makedirs(output_folder, exist_ok=True)
printed_ocr_output = os.path.join(output_folder, "printed")
handwritten_ocr_output = os.path.join(output_folder, "handwritten")

os.makedirs(printed_ocr_output, exist_ok=True)
os.makedirs(handwritten_ocr_output, exist_ok=True)
# ==============================
#  TESSERACT SETUP
# ==============================
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ==============================
#  TrOCR SETUP
# ==============================
device = "cuda" if torch.cuda.is_available() else "cpu"

processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")

model.to(device)
model.eval()   

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
#  HANDWRITTEN OCR (TrOCR)
# ==============================
def ocr_handwritten(image_path):
    try:
        image = Image.open(image_path).convert("RGB")
        image = image.resize((384, 384))  # speed optimization

        pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)

        generated_ids = model.generate(pixel_values, max_length=128)
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        return text
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return ""


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

# ==============================
#  PROCESS HANDWRITTEN DATASET
# ==============================
print("\n Processing Handwritten Invoices...")

for root, dirs, files in os.walk(handwritten_folder):
    for file in files:
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):

            path = os.path.join(root, file)
            text = ocr_handwritten(path)

            print(f"\n {file}")
            print(text)

            name = os.path.splitext(file)[0]
            save_text(handwritten_ocr_output,name, text)


print("\n OCR COMPLETED SUCCESSFULLY!")