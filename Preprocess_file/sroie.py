import cv2
import numpy as np
import os
import glob

def preprocess_image(image_path):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None

    img = cv2.GaussianBlur(img, (5, 5), 0)

    binary = cv2.adaptiveThreshold(
        img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        21, 10
    )

    return binary


# ---- PATHS ----
input_root = r"F:\SplitedDatasets\SROIE2019"
output_root = r"F:\Processed_sroie"

# ---- EXTENSIONS ----
extensions = ('*.jpg','*.jpeg','*.png','*.bmp','*.JPG','*.PNG')

# ---- GET FILES ----
files = []
for ext in extensions:
    files.extend(glob.glob(os.path.join(input_root, "**", ext), recursive=True))

print(f"Found {len(files)} images")

# ---- PROCESS LOOP ----
for file_path in files:
    processed = preprocess_image(file_path)

    if processed is not None:
        #  Extract train/test/val folder name
        parts = file_path.split(os.sep)

        # Find index of SROIE2019
        idx = parts.index("SROIE2019")

        # Next folder is train/test/val
        split_folder = parts[idx + 1]

        # Create same folder in output
        save_dir = os.path.join(output_root, split_folder)
        os.makedirs(save_dir, exist_ok=True)

        # Save image
        file_name = os.path.basename(file_path)
        save_path = os.path.join(save_dir, file_name)

        cv2.imwrite(save_path, processed)

print("\n Done with correct folder structure!")
