import os
import shutil
import random

# Path to your dataset
input_folder = r"F:\Handwritten_datasets"

# Output folder
output_folder = os.path.join(input_folder, "dataset_split")

train_ratio = 0.7
val_ratio = 0.15
test_ratio = 0.15

# Create folders
for folder in ["train", "val", "test"]:
    os.makedirs(os.path.join(output_folder, folder), exist_ok=True)

# Get all image files
files = [f for f in os.listdir(input_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]

random.shuffle(files)

total = len(files)
train_end = int(train_ratio * total)
val_end = int((train_ratio + val_ratio) * total)

train_files = files[:train_end]
val_files = files[train_end:val_end]
test_files = files[val_end:]

# Function to copy files
def copy_files(file_list, folder_name):
    for file in file_list:
        src = os.path.join(input_folder, file)
        dst = os.path.join(output_folder, folder_name, file)
        shutil.copy(src, dst)

copy_files(train_files, "train")
copy_files(val_files, "val")
copy_files(test_files, "test")

print(" Dataset split completed!")