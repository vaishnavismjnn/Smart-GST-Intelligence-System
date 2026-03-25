import os
import shutil

#  Root dataset
base_folder = r"F:\Invoice dataset"

#  Output 1 → F drive
merged_folder1 = r"F:\merged_dataset"

#  Output 2 → GitHub project
merged_folder2 = r"Datasets\merged_dataset"

os.makedirs(merged_folder1, exist_ok=True)
os.makedirs(merged_folder2, exist_ok=True)

count = 0
skipped = 0

for root, dirs, files in os.walk(base_folder):

    # Avoid copying from merged folders
    if merged_folder1 in root or merged_folder2 in root:
        continue

    for file in files:
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):

            src = os.path.join(root, file)

            filename = file

            # ----------- F DRIVE DEST -----------
            dst1 = os.path.join(merged_folder1, filename)

            i = 1
            while os.path.exists(dst1):
                name, ext = os.path.splitext(filename)
                dst1 = os.path.join(merged_folder1, f"{name}_{i}{ext}")
                i += 1

            # ----------- GITHUB DEST -----------
            dst2 = os.path.join(merged_folder2, os.path.basename(dst1))

            try:
                shutil.copy(src, dst1)
                shutil.copy(src, dst2)
                count += 1
            except Exception as e:
                print(f" Error copying {file}: {e}")
                skipped += 1

print(" Merge completed in BOTH locations!")
print("Total images merged:", count)
print("Skipped files:", skipped)