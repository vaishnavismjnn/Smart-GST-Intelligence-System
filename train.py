"""
train.py  –  LayoutLMv3 Fine-tuning for GST Invoice Extraction
===============================================================
Trains LayoutLMv3ForTokenClassification on preprocessed invoice
JSON + image pairs saved in PROCESSED_FOLDER / IMAGE_FOLDER.
"""

import os
import json
from PIL import Image
from torch.utils.data import Dataset
from transformers import Trainer, TrainingArguments

# ── Import everything from model.py ──────────────────────────
from model import label2id, load_model, load_processor

# ─────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────
PROCESSED_FOLDER = r"F:\newdataset\processed_dataset"
IMAGE_FOLDER      = r"F:\newdataset\images"

# ─────────────────────────────────────────
# LOAD PROCESSOR
# ─────────────────────────────────────────
processor = load_processor()


# ─────────────────────────────────────────
# DATASET CLASS
# ─────────────────────────────────────────
class InvoiceDataset(Dataset):
    def __init__(self, folder):
        self.files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.endswith(".json") and not f.startswith("_")
        ]

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        with open(self.files[idx]) as f:
            data = json.load(f)

        image_name = os.path.basename(self.files[idx]).replace(".json", ".png")
        image_path = os.path.join(IMAGE_FOLDER, image_name)
        image      = Image.open(image_path).convert("RGB")

        encoding = processor(
            image,
            data["words"],
            boxes=data["bboxes"],
            word_labels=[label2id[l.replace("I-", "B-")] for l in data["labels"]],
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        return {k: v.squeeze() for k, v in encoding.items()}


# ─────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────
dataset = InvoiceDataset(PROCESSED_FOLDER)
print(f" Total training samples: {len(dataset)}")


# ─────────────────────────────────────────
# LOAD MODEL  (base weights for training)
# ─────────────────────────────────────────
model = load_model()          # no checkpoint_path → loads microsoft/layoutlmv3-base


# ─────────────────────────────────────────
# TRAINING CONFIG
# ─────────────────────────────────────────
training_args = TrainingArguments(
    output_dir="./model",
    per_device_train_batch_size=2,
    num_train_epochs=3,
    learning_rate=5e-5,
    logging_steps=20,
    save_strategy="epoch",
    remove_unused_columns=False,
)


# ─────────────────────────────────────────
# TRAINER
# ─────────────────────────────────────────
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
)


# ─────────────────────────────────────────
# TRAIN
# ─────────────────────────────────────────
trainer.train()


# ─────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────
model.save_pretrained("./model")
processor.save_pretrained("./model")

print("\n TRAINING COMPLETE")
