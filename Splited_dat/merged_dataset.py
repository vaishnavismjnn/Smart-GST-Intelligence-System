import os
import shutil

#  Root dataset
base_folder = r"F:\Invoice dataset"

#  Output → ONLY F drive
merged_folder = r"F:\merged_dataset"

os.makedirs(merged_folder, exist_ok=True)

count = 0
skipped = 0

for root, dirs, files in os.walk(base_folder):

    # Avoid copying from merged folder itself
    if merged_folder in root:
        continue

    for file in files:
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):

            src = os.path.join(root, file)
            filename = file

            # Destination path
            dst = os.path.join(merged_folder, filename)

            # Handle duplicate names
            i = 1
            while os.path.exists(dst):
                name, ext = os.path.splitext(filename)
                dst = os.path.join(merged_folder, f"{name}_{i}{ext}")
                i += 1

            try:
                shutil.copy(src, dst)
                count += 1
            except Exception as e:
                print(f" Error copying {file}: {e}")
                skipped += 1

print(" Merge completed (LOCAL ONLY)")
print("Total images merged:", count)
print("Skipped files:", skipped)
