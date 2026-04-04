import shutil
from pathlib import Path

IMG_ROOT  = Path(r"F:\Printed_Images")
JSON_ROOT = Path(r"F:\layout_json_output")
OUT_ROOT  = Path(r"F:\TScript")

splits = ["train", "val", "test"]

for split in splits:
    print(f"\n Processing {split}...")

    for dataset in ["processed_fake_dataset", "processed_invoices", "SROIE_PROCESS"]:
        
        json_dir = JSON_ROOT / dataset / split
        img_dir  = IMG_ROOT  / dataset / split

        if not json_dir.exists() or not img_dir.exists():
            print(f" Missing {dataset}/{split}")
            continue

        for json_file in json_dir.rglob("*.json"):
            name = json_file.stem

            # find image
            img = None
            for ext in [".png", ".jpg", ".jpeg"]:
                matches = list(img_dir.rglob(name + ext))
                if matches:
                    img = matches[0]
                    break

            if not img:
                print(f" Missing image for {name}")
                continue

            # destination
            img_dst  = OUT_ROOT / split / "images" / img.name
            json_dst = OUT_ROOT / split / "annotations" / json_file.name

            img_dst.parent.mkdir(parents=True, exist_ok=True)
            json_dst.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy(img, img_dst)
            shutil.copy(json_file, json_dst)

print("\n Dataset prepared correctly")