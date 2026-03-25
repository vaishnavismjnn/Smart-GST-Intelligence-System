import os
import random
import shutil

# dataset path
input_folder = r"F:\final_invoices_dataset\final_invoices_dataset"

# Output path
output_folder = r"Datasets\split_dataset"
output_folder_1 = os.path.join(input_folder, "fake_dataset_split")

train_dir = os.path.join(output_folder, "train")
val_dir = os.path.join(output_folder, "val")
test_dir = os.path.join(output_folder, "test")

# Create folders
for folder in [train_dir, val_dir, test_dir]:
    os.makedirs(folder, exist_ok=True)

# Get all image files
images = [f for f in os.listdir(input_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]

# Shuffle
random.shuffle(images)

# Split ratios
train_ratio = 0.7
val_ratio = 0.2
test_ratio = 0.1

total = len(images)

train_split = int(train_ratio * total)
val_split = int((train_ratio + val_ratio) * total)

train_files = images[:train_split]
val_files = images[train_split:val_split]
test_files = images[val_split:]

# Copy function
def copy_files(files, destination):
    for file in files:
        src = os.path.join(input_folder, file)
        dst = os.path.join(destination, file)
        shutil.copy(src, dst)

# Copy data
copy_files(train_files, train_dir)
copy_files(val_files, val_dir)
copy_files(test_files, test_dir)

print("Dataset split completed!")
print("Train:", len(train_files))
print("Val:", len(val_files))
print("Test:", len(test_files))