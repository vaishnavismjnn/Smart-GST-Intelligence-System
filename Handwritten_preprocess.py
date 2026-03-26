import cv2
import os

input_folder = r"F:\SplitedDatasets\Handwritten_split_dataset"
output_folder = r"F:\Handwritten_processed"

os.makedirs(output_folder, exist_ok=True)

def preprocess_handwritten(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Smooth first 
    blur = cv2.medianBlur(gray, 3)

    # Adaptive threshold
    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    return clean

for root, dirs, files in os.walk(input_folder):
    for file in files:
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

print("Handwritten dataset processed successfully!")