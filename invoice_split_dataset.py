import os
import random
import shutil

#  Input (merged dataset)
input_folder = r"F:\merged_dataset"

#  Output
output_folder = r"F:\invoice_split_dataset"

train_dir = os.path.join(output_folder, "train")
val_dir = os.path.join(output_folder, "val")
test_dir = os.path.join(output_folder, "test")

# Create folders
for folder in [train_dir, val_dir, test_dir]:
    os.makedirs(folder, exist_ok=True)

# Get all image files
files = [f for f in os.listdir(input_folder)
         if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

print("Total images:", len(files))

# Shuffle
random.shuffle(files)

# Ratios
train_ratio = 0.7
val_ratio = 0.15
test_ratio = 0.15

# Split sizes
total = len(files)
train_end = int(train_ratio * total)
val_end = train_end + int(val_ratio * total)

train_files = files[:train_end]
val_files = files[train_end:val_end]
test_files = files[val_end:]

# Copy function
def copy_files(file_list, destination):
    for file in file_list:
        src = os.path.join(input_folder, file)
        dst = os.path.join(destination, file)
        shutil.copy2(src, dst)

# Copy data
copy_files(train_files, train_dir)
copy_files(val_files, val_dir)
copy_files(test_files, test_dir)

print(" Dataset Split Completed!")
print(f"Train: {len(train_files)}")
print(f"Validation: {len(val_files)}")
print(f"Test: {len(test_files)}")