import os
import random
import shutil

#  Original SROIE train (F drive)
base_path = r"F:\SROIE dataset\SROIE2019\train"

img_path = os.path.join(base_path, "img")
box_path = os.path.join(base_path, "box")
entities_path = os.path.join(base_path, "entities")

#  Output → ONLY F drive validation
val_base = r"F:\SROIE dataset\SROIE2019\val"

def create_dirs(base):
    return (
        os.path.join(base, "img"),
        os.path.join(base, "box"),
        os.path.join(base, "entities")
    )

val_img, val_box, val_entities = create_dirs(val_base)

# Create folders
for folder in [val_img, val_box, val_entities]:
    os.makedirs(folder, exist_ok=True)

# Get image files
files = [f for f in os.listdir(img_path) if f.endswith(".jpg")]

random.shuffle(files)

# 20% validation
val_size = int(0.2 * len(files))
val_files = files[:val_size]

# Copy ONLY to F drive
for file in val_files:
    name = file.replace(".jpg", "")

    # IMAGE
    shutil.copy(os.path.join(img_path, file), os.path.join(val_img, file))

    # BOX
    shutil.copy(os.path.join(box_path, name + ".txt"),
                os.path.join(val_box, name + ".txt"))

    # ENTITIES
    shutil.copy(os.path.join(entities_path, name + ".txt"),
                os.path.join(val_entities, name + ".txt"))

print(" Validation dataset created (LOCAL ONLY)")
print(f"Validation samples: {len(val_files)}")
