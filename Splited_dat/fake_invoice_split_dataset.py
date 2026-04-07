import os
import random
import shutil

input_folder = r"F:\final_invoices_dataset\final_invoices_dataset"
output_folder1 = r"F:\fake_split_dataset"

train_dir1 = os.path.join(output_folder1, "train")
val_dir1 = os.path.join(output_folder1, "val")
test_dir1 = os.path.join(output_folder1, "test")

for folder in [train_dir1, val_dir1, test_dir1]:
    os.makedirs(folder, exist_ok=True)

images = [f for f in os.listdir(input_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]

random.shuffle(images)

train_ratio = 0.7
val_ratio = 0.2

total = len(images)

train_split = int(train_ratio * total)
val_split = int((train_ratio + val_ratio) * total)

train_files = images[:train_split]
val_files = images[train_split:val_split]
test_files = images[val_split:]

def copy_files(files, dest):
    for file in files:
        src = os.path.join(input_folder, file)
        shutil.copy(src, os.path.join(dest, file))

copy_files(train_files, train_dir1)
copy_files(val_files, val_dir1)
copy_files(test_files, test_dir1)

print("Dataset split completed!")
print("Train:", len(train_files))
print("Val:", len(val_files))
print("Test:", len(test_files))
