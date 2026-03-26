import cv2
import os
import numpy as np
from tqdm import tqdm

input_root = r"F:\SplitedDatasets"          
output_root = r"F:\processed_dataset"

def deskew(image):
    coords = np.column_stack(np.where(image > 0))
    angle = cv2.minAreaRect(coords)[-1]

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)

    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, M, (w, h),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)

def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Contrast Enhancement (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)

    # Noise Removal
    denoised = cv2.GaussianBlur(enhanced, (5, 5), 0)

    # Binarization
    thresh = cv2.threshold(denoised, 0, 255,
                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    # Deskew
    final = deskew(thresh)

    return final

# LOOP THROUGH ALL FOLDERS
for root, dirs, files in os.walk(input_root):
    for file in tqdm(files):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):

            input_path = os.path.join(root, file)

            # Maintain folder structure
            relative_path = os.path.relpath(root, input_root)
            output_dir = os.path.join(output_root, relative_path)
            os.makedirs(output_dir, exist_ok=True)

            output_path = os.path.join(output_dir, file)

            img = cv2.imread(input_path)

            if img is None:
                continue

            processed = preprocess(img)
            cv2.imwrite(output_path, processed)

print(" All 11672 images processed successfully!")