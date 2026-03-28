import cv2
import numpy as np
import os

input_folder = r"F:\SplitedDatasets\Handwritten_split_dataset"
output_folder = r"F:\Handwritten_processed"

os.makedirs(output_folder, exist_ok=True)


def preprocess_handwritten(img):

    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Light smoothing (remove dots)
    blur = cv2.medianBlur(gray, 3)

    # 3. Adaptive threshold (balanced)
    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15, 5   # less dark than before
    )

    # 4. Remove small noise
    kernel = np.ones((2,2), np.uint8)
    clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    # ---------------------------
    # 5. SIMPLE DESKEW (more reliable)
    coords = np.column_stack(np.where(gray < 150))

    if coords.size > 0:
        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = 90 + angle
        else:
            angle = angle

        (h, w) = clean.shape[:2]
        center = (w // 2, h // 2)

        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        clean = cv2.warpAffine(
            clean, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255
        )

    # ---------------------------
    # 6. Crop content area
    coords = cv2.findNonZero(255 - clean)

    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        clean = clean[y:y+h, x:x+w]

    return clean


# PROCESS LOOP
for root, dirs, files in os.walk(input_folder):
    for file in files:

        if not file.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue

        input_path = os.path.join(root, file)

        img = cv2.imread(input_path)
        if img is None:
            continue

        processed = preprocess_handwritten(img)

        # Maintain folder structure
        relative_path = os.path.relpath(input_path, input_folder)
        output_path = os.path.join(output_folder, relative_path)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, processed)

print(" Clean preprocessing done!")