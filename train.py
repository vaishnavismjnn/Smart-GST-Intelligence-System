"""
LayoutLMv3 Fine-Tuning Script for Indian GST Invoice Field Extraction

Pipeline: OCR (Tesseract) → Layout Detection → LayoutLMv3 Fine-Tuning


Requirements:
    pip install transformers datasets seqeval pillow pytesseract torch torchvision

Folder structure expected:
    data/
      train/
        images/        # invoice images (.jpg / .png)
        annotations/   # one JSON per image (same filename)
      val/
        images/
        annotations/

Annotation JSON format (one file per invoice image):
    {
      "words": ["GSTIN", "29ABCDE1234F1Z5", "Invoice", "No", "INV-001", ...],
      "bboxes": [[x1,y1,x2,y2], ...],   # absolute pixel coords
      "labels": ["B-GSTIN", "I-GSTIN", "B-INVOICE_NO", "I-INVOICE_NO", "I-INVOICE_NO", ...]
    }

Supported labels (BIO scheme):
    B-/I- prefix for: GSTIN, SELLER_NAME, BUYER_NAME, INVOICE_NO,
                      INVOICE_DATE, HSN_CODE, TAXABLE_AMT, CGST, SGST,
                      IGST, TOTAL_AMT, ITEM_DESC
    O  → tokens that don't belong to any field
"""

import os
import json
import torch
import numpy as np
from pathlib import Path
from PIL import Image
from torch.utils.data import Dataset
from transformers import (
    LayoutLMv3Processor,
    LayoutLMv3ForTokenClassification,
    TrainingArguments,
    Trainer,
)
from datasets import load_metric


# 1.  LABEL DEFINITIONS


# All field types in your GST invoices
FIELD_TYPES = [
    "GSTIN", "SELLER_NAME", "BUYER_NAME", "INVOICE_NO", "INVOICE_DATE",
    "HSN_CODE", "TAXABLE_AMT", "CGST", "SGST", "IGST", "TOTAL_AMT", "ITEM_DESC"
]

# Build full BIO label list
LABEL_LIST = ["O"]
for field in FIELD_TYPES:
    LABEL_LIST.append(f"B-{field}")
    LABEL_LIST.append(f"I-{field}")

LABEL2ID = {label: idx for idx, label in enumerate(LABEL_LIST)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}

print(f" Total labels: {len(LABEL_LIST)}")
print(f"   Labels: {LABEL_LIST}")


# 2.  DATASET CLASS


class GSTInvoiceDataset(Dataset):
    """
    Loads invoice images + annotation JSONs and prepares inputs
    for LayoutLMv3 (words, bboxes normalized to 0-1000, labels).
    """

    def __init__(self, image_dir: str, annotation_dir: str, processor, max_length: int = 512):
        self.image_dir = Path(image_dir)
        self.annotation_dir = Path(annotation_dir)
        self.processor = processor
        self.max_length = max_length

        # Match images to annotation files
        self.samples = []
        for ann_path in sorted(self.annotation_dir.glob("*.json")):
            img_path = self.image_dir / (ann_path.stem + ".jpg")
            if not img_path.exists():
                img_path = self.image_dir / (ann_path.stem + ".png")
            if img_path.exists():
                self.samples.append((img_path, ann_path))
            else:
                print(f"  No image found for {ann_path.name}, skipping.")

        print(f" Loaded {len(self.samples)} samples from {image_dir}")

    def __len__(self):
        return len(self.samples)

    def normalize_bbox(self, bbox, width, height):
        """Normalize bbox from pixel coords to 0-1000 range (LayoutLMv3 requirement)."""
        x1, y1, x2, y2 = bbox
        return [
            int(1000 * x1 / width),
            int(1000 * y1 / height),
            int(1000 * x2 / width),
            int(1000 * y2 / height),
        ]

    def __getitem__(self, idx):
        img_path, ann_path = self.samples[idx]

        # Load image
        image = Image.open(img_path).convert("RGB")
        width, height = image.size

        # Load annotation
        with open(ann_path, "r", encoding="utf-8") as f:
            ann = json.load(f)

        words = ann["words"]
        bboxes = [self.normalize_bbox(b, width, height) for b in ann["bboxes"]]
        word_labels = [LABEL2ID.get(l, 0) for l in ann["labels"]]

        # LayoutLMv3 processor handles tokenization + bbox alignment
        encoding = self.processor(
            image,
            words,
            boxes=bboxes,
            word_labels=word_labels,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        # Remove batch dimension added by processor
        return {k: v.squeeze(0) for k, v in encoding.items()}

# 3.  METRICS

seqeval = load_metric("seqeval")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)

    true_labels, true_predictions = [], []
    for pred_seq, label_seq in zip(predictions, labels):
        true_label_row, true_pred_row = [], []
        for pred_token, label_token in zip(pred_seq, label_seq):
            if label_token == -100:   # special tokens are ignored
                continue
            true_label_row.append(ID2LABEL[label_token])
            true_pred_row.append(ID2LABEL[pred_token])
        true_labels.append(true_label_row)
        true_predictions.append(true_pred_row)

    results = seqeval.compute(predictions=true_predictions, references=true_labels)
    return {
        "precision": results["overall_precision"],
        "recall":    results["overall_recall"],
        "f1":        results["overall_f1"],
        "accuracy":  results["overall_accuracy"],
    }

# 4.  MAIN TRAINING FUNCTION

def train(
    train_image_dir:  str = "data/train/images",
    train_ann_dir:    str = "data/train/annotations",
    val_image_dir:    str = "data/val/images",
    val_ann_dir:      str = "data/val/annotations",
    output_dir:       str = "models/layoutlmv3-gst-invoices",
    base_model:       str = "microsoft/layoutlmv3-base",
    num_epochs:       int = 10,
    batch_size:       int = 2,          # keep low for GPU memory
    learning_rate:    float = 5e-5,
    max_length:       int = 512,
):
    print("\n Starting LayoutLMv3 Fine-Tuning for GST Invoices")
    print(f"   Base model : {base_model}")
    print(f"   Epochs     : {num_epochs}")
    print(f"   Batch size : {batch_size}")
    print(f"   Output dir : {output_dir}\n")

    # ── Processor (tokenizer + image processor) ──
    processor = LayoutLMv3Processor.from_pretrained(base_model, apply_ocr=False)
    # apply_ocr=False because WE supply words+bboxes from Tesseract

    # ── Datasets ──
    train_dataset = GSTInvoiceDataset(train_image_dir, train_ann_dir, processor, max_length)
    val_dataset   = GSTInvoiceDataset(val_image_dir,   val_ann_dir,   processor, max_length)

    # ── Model ──
    model = LayoutLMv3ForTokenClassification.from_pretrained(
        base_model,
        num_labels=len(LABEL_LIST),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    # ── Training Arguments ──
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        warmup_ratio=0.1,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_dir=os.path.join(output_dir, "logs"),
        logging_steps=10,
        save_total_limit=2,
        fp16=torch.cuda.is_available(),   # mixed precision on GPU
        report_to="none",                 # change to "wandb" if you use W&B
    )

    # ── Trainer ──
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=processor,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    # ── Save final model ──
    trainer.save_model(output_dir)
    processor.save_pretrained(output_dir)
    print(f"\n Model saved to: {output_dir}")

    return trainer

# 5.  INFERENCE HELPER (after training)

def extract_fields(image_path: str, words: list, bboxes: list, model_dir: str = "models/layoutlmv3-gst-invoices"):
    """
    Run inference on a single invoice after fine-tuning.

    Args:
        image_path : path to invoice image
        words      : list of words from Tesseract OCR
        bboxes     : list of [x1,y1,x2,y2] bboxes (absolute pixel coords)
        model_dir  : path to your saved fine-tuned model

    Returns:
        dict of extracted fields, e.g. {"GSTIN": "29ABCDE...", "TOTAL_AMT": "5400", ...}
    """
    processor = LayoutLMv3Processor.from_pretrained(model_dir, apply_ocr=False)
    model     = LayoutLMv3ForTokenClassification.from_pretrained(model_dir)
    model.eval()

    image  = Image.open(image_path).convert("RGB")
    width, height = image.size

    # Normalize bboxes
    norm_bboxes = [
        [int(1000*x1/width), int(1000*y1/height), int(1000*x2/width), int(1000*y2/height)]
        for x1, y1, x2, y2 in bboxes
    ]

    encoding = processor(
        image, words, boxes=norm_bboxes,
        return_tensors="pt", truncation=True, max_length=512
    )

    with torch.no_grad():
        outputs = model(**encoding)

    predictions = outputs.logits.argmax(-1).squeeze().tolist()
    input_ids   = encoding["input_ids"].squeeze().tolist()

    tokens = processor.tokenizer.convert_ids_to_tokens(input_ids)
    labels = [ID2LABEL.get(p, "O") for p in predictions]

    # ── Aggregate tokens → fields ──
    extracted = {}
    current_field, current_tokens = None, []

    for token, label in zip(tokens, labels):
        if token in ["<s>", "</s>", "<pad>"]:
            continue
        if label.startswith("B-"):
            if current_field:
                extracted[current_field] = processor.tokenizer.convert_tokens_to_string(current_tokens).strip()
            current_field  = label[2:]
            current_tokens = [token]
        elif label.startswith("I-") and current_field == label[2:]:
            current_tokens.append(token)
        else:
            if current_field:
                extracted[current_field] = processor.tokenizer.convert_tokens_to_string(current_tokens).strip()
            current_field, current_tokens = None, []

    if current_field:
        extracted[current_field] = processor.tokenizer.convert_tokens_to_string(current_tokens).strip()

    return extracted

# 6.  ENTRY POINT

if __name__ == "__main__":
    # ── Train ──
    trainer = train(
        train_image_dir="data/train/images",
        train_ann_dir="data/train/annotations",
        val_image_dir="data/val/images",
        val_ann_dir="data/val/annotations",
        output_dir="models/layoutlmv3-gst-invoices",
        num_epochs=10,
        batch_size=2,
        learning_rate=5e-5,
    )

    # ── Quick inference test (replace with your real image + OCR output) ──
    # words  = ["GSTIN", "29ABCDE1234F1Z5", "Invoice", "No", "INV-001"]
    # bboxes = [[10,10,80,25], [85,10,200,25], [10,30,60,45], [65,30,80,45], [85,30,150,45]]
    # fields = extract_fields("data/val/images/sample.jpg", words, bboxes)
    # print("Extracted fields:", fields)
