import shutil
from pathlib import Path

JSON_DIR = Path(r"F:\layout_json_output\processed_fake_dataset\val")
IMG_DIR  = Path(r"F:\Dataset processed\processed_fake_dataset\val")
OUT_DIR  = Path(r"F:\Script\val")

for json_file in JSON_DIR.rglob("*.json"):
    name = json_file.stem

    # find corresponding image
    img = None
    for ext in [".png", ".jpg", ".jpeg"]:
        p = IMG_DIR / (name + ext)
        if p.exists():
            img = p
            break

    if not img:
        print(f" Missing image for {name}")
        continue

    # destination paths
    img_dst  = OUT_DIR / "images" / img.name
    json_dst = OUT_DIR / "annotations" / json_file.name

    img_dst.parent.mkdir(parents=True, exist_ok=True)
    json_dst.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy(img, img_dst)
    shutil.copy(json_file, json_dst)

print(" Val dataset prepared")