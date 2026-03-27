from PIL import Image
import os
from tqdm import tqdm

input_root = r"F:\SplitedDatasets"
bad_folder = r"F:\bad_images"

os.makedirs(bad_folder, exist_ok=True)

skipped = 0

for root, dirs, files in os.walk(input_root):
    for file in tqdm(files):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):

            path = os.path.join(root, file)

            try:
                with Image.open(path) as img:
                    img.verify()   # check corruption

            except Exception:
                print(f"Moved corrupted: {path}")

                new_path = os.path.join(bad_folder, file)

                base, ext = os.path.splitext(file)
                count = 1
                while os.path.exists(new_path):
                    new_path = os.path.join(bad_folder, f"{base}_{count}{ext}")
                    count += 1

                os.rename(path, new_path)
                skipped += 1

print(f"Total corrupted images moved: {skipped}")