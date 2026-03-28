import cv2
import numpy as np
import os

#  PATHS
input_folder = r"F:\SplitedDatasets\fake_split_dataset"
output_folder = r"F:\processed_fake_dataset"

os.makedirs(output_folder, exist_ok=True)


#  PREPROCESS FUNCTION
def preprocess_image(image_path):
    img = cv2.imread(image_path)

    if img is None:
        return None

    img = cv2.resize(img, None, fx=1.2, fy=1.2)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(blur)

    thresh = cv2.adaptiveThreshold(
        contrast, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )

    return thresh


#  PROCESS LOOP
count = 0

for root, dirs, files in os.walk(input_folder):
    for file in files:
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):

            input_path = os.path.join(root, file)

            #  IMPORTANT: preserve folder structure
            relative_path = os.path.relpath(input_path, input_folder)

            output_path = os.path.join(output_folder, relative_path)

            # create same subfolder (train/test/val)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            processed = preprocess_image(input_path)

            if processed is None:
                continue

            cv2.imwrite(output_path, processed)
            count += 1

            if count % 100 == 0:
                print(f"Processed {count} images...")


print("\n Preprocessing Completed!")
print(f"Total images processed: {count}")