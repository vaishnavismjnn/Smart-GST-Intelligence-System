import os
import random
import shutil

#  Original SROIE train (F drive)
base_path = r"F:\SROIE dataset\SROIE2019\train"

img_path = os.path.join(base_path, "img")
box_path = os.path.join(base_path, "box")
entities_path = os.path.join(base_path, "entities")

#  Output 1 → F drive validation
val_base_1 = r"F:\SROIE dataset\SROIE2019\val"

#  Output 2 → GitHub validation
val_base_2 = r"Datasets\SROIE\val"

def create_dirs(base):
    return (
        os.path.join(base, "img"),
        os.path.join(base, "box"),
        os.path.join(base, "entities")
    )

val_img1, val_box1, val_entities1 = create_dirs(val_base_1)
val_img2, val_box2, val_entities2 = create_dirs(val_base_2)

# Create folders
for folder in [val_img1, val_box1, val_entities1,
               val_img2, val_box2, val_entities2]:
    os.makedirs(folder, exist_ok=True)

# Get image files
files = [f for f in os.listdir(img_path) if f.endswith(".jpg")]

random.shuffle(files)

# 20% validation
val_size = int(0.2 * len(files))
val_files = files[:val_size]

# Copy to BOTH locations
for file in val_files:
    name = file.replace(".jpg", "")

    # IMAGE
    src_img = os.path.join(img_path, file)
    shutil.copy(src_img, os.path.join(val_img1, file))
    shutil.copy(src_img, os.path.join(val_img2, file))

    # BOX
    src_box = os.path.join(box_path, name + ".txt")
    shutil.copy(src_box, os.path.join(val_box1, name + ".txt"))
    shutil.copy(src_box, os.path.join(val_box2, name + ".txt"))

    # ENTITIES
    src_ent = os.path.join(entities_path, name + ".txt")
    shutil.copy(src_ent, os.path.join(val_entities1, name + ".txt"))
    shutil.copy(src_ent, os.path.join(val_entities2, name + ".txt"))

print("Validation dataset created in BOTH locations!")
print(f"Validation samples: {len(val_files)}")