import os
import shutil
import random

input_folder = r"F:\Handwritten_datasets"
output_folder = r"F:\Handwritten_datasets\Handwritten_split_dataset"

train_ratio = 0.7
val_ratio = 0.15

for folder in ["train", "val", "test"]:
    os.makedirs(os.path.join(output_folder, folder), exist_ok=True)

# Get all images (including subfolders)
files = []
for root, dirs, filenames in os.walk(input_folder):
    for file in filenames:
        if file.endswith(('.png', '.jpg', '.jpeg')):
            files.append(os.path.join(root, file))

random.shuffle(files)

total = len(files)
train_end = int(train_ratio * total)
val_end = int((train_ratio + val_ratio) * total)

train_files = files[:train_end]
val_files = files[train_end:val_end]
test_files = files[val_end:]

def copy_files(file_list, folder_name):
    for file in file_list:
        dst = os.path.join(output_folder, folder_name, os.path.basename(file))
        shutil.copy(file, dst)

copy_files(train_files, "train")
copy_files(val_files, "val")
copy_files(test_files, "test")

print("Dataset split completed!")
print("Train:", len(train_files))
print("Val:", len(val_files))
print("Test:", len(test_files))