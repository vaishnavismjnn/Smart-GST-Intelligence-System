import cv2
import numpy as np
import os

#  PATHS
input_root = r"F:\SplitedDatasets\invoice_split_dataset"
output_root = r"F:\processed_invoices"

os.makedirs(output_root, exist_ok=True)


#  PREPROCESS FUNCTION (WITH DESKEW)
def preprocess_image(image_path):
    img = cv2.imread(image_path)

    if img is None:
        return None

    # Resize
    img = cv2.resize(img, None, fx=1.2, fy=1.2)

    # Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Blur
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # CLAHE (contrast)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(blur)

    # Threshold
    thresh = cv2.adaptiveThreshold(
        contrast,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        11,
        2
    )

    #  DESKEW (fix rotation)
    coords = np.column_stack(np.where(thresh == 0))
    if coords.size > 0:
        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        (h, w) = thresh.shape[:2]
        center = (w // 2, h // 2)

        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        thresh = cv2.warpAffine(
            thresh,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255
        )

    return thresh


#  PROCESS LOOP (WITH FOLDER STRUCTURE)
count = 0

for root, dirs, files in os.walk(input_root):
    for file in files:
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):

            input_path = os.path.join(root, file)

            #  Get relative path (train/test/val)
            relative_path = os.path.relpath(input_path, input_root)

            #  Create same folder in output
            save_path = os.path.join(output_root, relative_path)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            processed = preprocess_image(input_path)

            if processed is None:
                continue

            cv2.imwrite(save_path, processed)
            count += 1

            if count % 100 == 0:
                print(f"Processed {count} images...")

print("\n Preprocessing Completed!")
print(f"Total images processed: {count}")