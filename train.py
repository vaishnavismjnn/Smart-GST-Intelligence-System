import torch
print(torch.cuda.is_available())

from google.colab import drive
drive.mount('/content/drive')

!pip install transformers pillow pytesseract torch torchvision evaluate

!apt-get install tesseract-ocr -y

import os
import json
import torch
import torch.nn as nn
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
import evaluate

FIELD_TYPES = [
    "GSTIN", "INVOICE_NO", "INVOICE_DATE",
    "TAXABLE_AMOUNT", "GST_AMOUNT", "TOTAL_AMOUNT", "MERCHANT",
]

LABEL_LIST = ["O"]
for field in FIELD_TYPES:
    LABEL_LIST.append(f"B-{field}")
    LABEL_LIST.append(f"I-{field}")

LABEL2ID = {label: idx for idx, label in enumerate(LABEL_LIST)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}

print(f" Total labels: {len(LABEL_LIST)}")
print(f"   Labels: {LABEL_LIST}")



def validate_bboxes(bboxes, words, ann_path):
    """
    Validate bboxes — skip invalid ones instead of crashing.
    Returns a boolean mask of which words to keep.
    """
    valid_mask = []
    for i, bbox in enumerate(bboxes):
        word = words[i] if i < len(words) else "?"

        # Check 1: Must have 4 values
        if len(bbox) != 4:
            print(f"  [{ann_path}] bbox index {i} (word='{word}') "
                  f"wrong length {len(bbox)} — skipping word.")
            valid_mask.append(False)
            continue

        x1, y1, x2, y2 = bbox

        # Check 2: Must be in 0-1000 range
        if any(v < 0 or v > 1000 for v in [x1, y1, x2, y2]):
            print(f"  [{ann_path}] bbox index {i} (word='{word}') "
                  f"not normalized 0-1000: {bbox} — skipping word.")
            valid_mask.append(False)
            continue

        # Check 3: x1 < x2 and y1 < y2
        if x1 >= x2 or y1 >= y2:
            # Silent skip — this is common OCR noise (zero-size boxes)
            valid_mask.append(False)
            continue

        valid_mask.append(True)

    return valid_mask


class GSTInvoiceDataset(Dataset):

    def __init__(self, image_dir, annotation_dir, processor, max_length=512):
        self.image_dir      = Path(image_dir)
        self.annotation_dir = Path(annotation_dir)
        self.processor      = processor
        self.max_length     = max_length

        self.samples = []
        skipped = 0

        for ann_path in sorted(self.annotation_dir.glob("*.json")):
            img_path = None
            for ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]:
                candidate = self.image_dir / (ann_path.stem + ext)
                if candidate.exists():
                    img_path = candidate
                    break

            if img_path is None:
                try:
                    with open(ann_path, "r", encoding="utf-8") as f:
                        tmp = json.load(f)
                    json_img = tmp.get("image", "")
                    if json_img and Path(json_img).exists():
                        img_path = Path(json_img)
                    else:
                        print(f"  Skipping {ann_path.name} — image not found.")
                        skipped += 1
                        continue
                except Exception:
                    print(f" Skipping {ann_path.name} — could not read JSON.")
                    skipped += 1
                    continue

            # ── Pre-validate: skip JSONs with no valid words ──
            try:
                with open(ann_path, "r", encoding="utf-8") as f:
                    tmp = json.load(f)

                if "layout" not in tmp or "words" not in tmp["layout"]:
                    print(f" Skipping {ann_path.name} — missing layout.words.")
                    skipped += 1
                    continue

                # Filter empty words
                words_data = [
                    w for w in tmp["layout"]["words"]
                    if w.get("text", "").strip()
                ]

                if not words_data:
                    print(f"  Skipping {ann_path.name} — no valid words.")
                    skipped += 1
                    continue

                # Filter bad bboxes
                words  = [w["text"] for w in words_data]
                bboxes = [w["bbox"]  for w in words_data]
                valid_mask = validate_bboxes(bboxes, words, ann_path.name)
                valid_words = [w for w, v in zip(words, valid_mask) if v]

                if not valid_words:
                    print(f"  Skipping {ann_path.name} — no words left after bbox filter.")
                    skipped += 1
                    continue

            except Exception as e:
                print(f"  Skipping {ann_path.name} — error during pre-validation: {e}")
                skipped += 1
                continue

            self.samples.append((img_path, ann_path))

        print(f" Loaded  : {len(self.samples)} samples from {annotation_dir}")
        if skipped:
            print(f"  Skipped : {skipped} samples (bad or empty)")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, ann_path = self.samples[idx]

        with open(ann_path, "r", encoding="utf-8") as f:
            ann = json.load(f)

        image = Image.open(img_path).convert("RGB")

        words_data = [
            w for w in ann["layout"]["words"]
            if w.get("text", "").strip()
        ]

        words       = [w["text"]                             for w in words_data]
        bboxes      = [w["bbox"]                             for w in words_data]
        word_labels = [LABEL2ID.get(w.get("label", "O"), 0) for w in words_data]

        valid_mask  = validate_bboxes(bboxes, words, ann_path.name)
        words       = [w for w, v in zip(words,       valid_mask) if v]
        bboxes      = [b for b, v in zip(bboxes,      valid_mask) if v]
        word_labels = [l for l, v in zip(word_labels, valid_mask) if v]

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

        return {k: v.squeeze(0) for k, v in encoding.items()}


!pip install evaluate seqeval

seqeval = evaluate.load("seqeval")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions    = np.argmax(logits, axis=-1)

    true_labels, true_predictions = [], []
    for pred_seq, label_seq in zip(predictions, labels):
        true_label_row, true_pred_row = [], []
        for p, l in zip(pred_seq, label_seq):
            if l == -100:
                continue
            true_label_row.append(ID2LABEL[l])
            true_pred_row.append(ID2LABEL[p])
        true_labels.append(true_label_row)
        true_predictions.append(true_pred_row)

    results = seqeval.compute(predictions=true_predictions, references=true_labels)
    return {
        "precision": results["overall_precision"],
        "recall"   : results["overall_recall"],
        "f1"       : results["overall_f1"],
        "accuracy" : results["overall_accuracy"],
    }


class WeightedTrainer(Trainer):

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels  = inputs.get("labels")
        outputs = model(**inputs)
        logits  = outputs.logits

        weights = torch.ones(len(LABEL_LIST), device=logits.device)
        for idx, label in ID2LABEL.items():
            if label != "O":
                weights[idx] = 3.0

        loss_fn = nn.CrossEntropyLoss(weight=weights, ignore_index=-100)
        loss    = loss_fn(logits.view(-1, len(LABEL_LIST)), labels.view(-1))

        return (loss, outputs) if return_outputs else loss


def verify_dataset(ann_dir, img_dir):
    """Run this once before training/inference to catch mismatches early."""
    ann_files = sorted(f for f in os.listdir(ann_dir) if f.endswith(".json"))
    issues = []

    for ann_file in ann_files:
        with open(os.path.join(ann_dir, ann_file)) as f:
            ann = json.load(f)

        stem = ann["image"].replace("\\", "/").split("/")[-1].rsplit(".", 1)[0]
        matches = [f for f in os.listdir(img_dir) if f.rsplit(".", 1)[0] == stem]

        if len(matches) == 0:
            issues.append(f" MISSING image for {ann_file}  (stem: {stem})")
        elif len(matches) > 1:
            issues.append(f"  DUPLICATE images for {ann_file}: {matches}")

    if issues:
        print("Dataset issues found:")
        for i in issues: print(" ", i)
    else:
        print(f" All {len(ann_files)} annotations matched cleanly.")

verify_dataset(ann_dir, img_dir)


def train(
    train_image_dir = "/content/drive/MyDrive/TScript/train/images",
    train_ann_dir   = "/content/drive/MyDrive/TScript/train/annotations",
    val_image_dir   = "/content/drive/MyDrive/TScript/val/images",
    val_ann_dir     = "/content/drive/MyDrive/TScript/val/annotations",
    output_dir      = "/content/drive/MyDrive/model",
    base_model      = "microsoft/layoutlmv3-base",
    num_epochs      = 3,
    batch_size      = 1,
    learning_rate   = 5e-5,
    max_length      = 512,
):
    print(f"\n Starting LayoutLMv3 Fine-Tuning")
    print(f"   Base model : {base_model}")
    print(f"   Epochs     : {num_epochs}")
    print(f"   Batch size : {batch_size}")
    print(f"   Device     : {'GPU ' if torch.cuda.is_available() else 'CPU  (slow)'}")
    print(f"   Output dir : {output_dir}\n")

    processor     = LayoutLMv3Processor.from_pretrained(base_model, apply_ocr=False)
    train_dataset = GSTInvoiceDataset(train_image_dir, train_ann_dir, processor, max_length)
    val_dataset   = GSTInvoiceDataset(val_image_dir,   val_ann_dir,   processor, max_length)

    model = LayoutLMv3ForTokenClassification.from_pretrained(
        base_model,
        num_labels=len(LABEL_LIST),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        warmup_steps=100, 
        weight_decay=0.01,
        eval_strategy="epoch",        # ← FIXED (was evaluation_strategy)
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_dir=os.path.join(output_dir, "logs"),
        logging_steps=10,
        save_total_limit=2,
        fp16=torch.cuda.is_available(),
        report_to="none",
    )

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        processing_class=processor,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    trainer.save_model(output_dir)
    processor.save_pretrained(output_dir)
    print(f"\n Model saved to: {output_dir}")
    return trainer


trainer = train(
    train_image_dir = "/content/drive/MyDrive/TScript/train/images",
    train_ann_dir   = "/content/drive/MyDrive/TScript/train/annotations",
    val_image_dir   = "/content/drive/MyDrive/TScript/val/images",
    val_ann_dir     = "/content/drive/MyDrive/TScript/val/annotations",
    output_dir      = "/content/drive/MyDrive/model",
    num_epochs      = 7,
    batch_size      = 1,
    learning_rate   = 5e-5,
)


from pathlib import Path

model_dir = "/content/drive/MyDrive/model"

# Safety check — don't load if training not done yet
if not Path(model_dir).exists():
    raise FileNotFoundError(
        f"Model folder '{model_dir}' not found.\n"
        f"Please run Cell 10 (training) first and wait for it to complete."
    )

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

inference_processor = LayoutLMv3Processor.from_pretrained(model_dir, apply_ocr=False)
inference_model     = LayoutLMv3ForTokenClassification.from_pretrained(model_dir)
inference_model.to(device)
inference_model.eval()

print(f" Model loaded on: {device}")


def extract_fields(image_path, words, bboxes, model, processor):
    """
    Run inference on a single invoice.

    Args:
        image_path : path to invoice image
        words      : list of word strings from ann['layout']['words']
        bboxes     : list of [x1,y1,x2,y2] already normalized 0-1000
        model      : loaded LayoutLMv3ForTokenClassification
        processor  : loaded LayoutLMv3Processor

    Returns:
        dict: e.g. {"GSTIN": "54BAUFG5524F1Z5", "TOTAL_AMOUNT": "8493.64"}
    """
    validate_bboxes(bboxes, words, "inference_input")

    image    = Image.open(image_path).convert("RGB")
    encoding = processor(
        image, words, boxes=bboxes,
        return_tensors="pt", truncation=True, max_length=512
    )

    # Fix 2: Move tensors to GPU/CPU device
    encoding = {k: v.to(device) for k, v in encoding.items()}

    with torch.no_grad():
        outputs = model(**encoding)

    predictions = outputs.logits.argmax(-1).squeeze().tolist()
    input_ids   = encoding["input_ids"].squeeze().tolist()
    tokens      = processor.tokenizer.convert_ids_to_tokens(input_ids)
    labels      = [ID2LABEL.get(p, "O") for p in predictions]

    extracted = {}
    current_field, current_tokens = None, []

    for token, label in zip(tokens, labels):
        # Fix 4: Skip ALL special tokens properly
        if token.startswith("<"):
            continue

        # Fix 3: Clean Ġ character from RoBERTa-style tokenizer
        clean_token = token.replace("Ġ", "")

        if label.startswith("B-"):
            if current_field:
                extracted[current_field] = processor.tokenizer.convert_tokens_to_string(
                    current_tokens).strip()
            current_field  = label[2:]
            current_tokens = [clean_token]          # Fix 3

        elif label.startswith("I-") and current_field == label[2:]:
            current_tokens.append(clean_token)      # Fix 3

        else:
            if current_field:
                extracted[current_field] = processor.tokenizer.convert_tokens_to_string(
                    current_tokens).strip()
            current_field, current_tokens = None, []

    if current_field:
        extracted[current_field] = processor.tokenizer.convert_tokens_to_string(
            current_tokens).strip()

    return extracted


def evaluate_test_set(
    test_image_dir = "/content/drive/MyDrive/TScript/test/images",
    test_ann_dir   = "/content/drive/MyDrive/TScript/test/annotations",
    model_dir      = "/content/drive/MyDrive/model",
    max_length     = 512,
):
    print("\n Evaluating on Test Set...")

    # Fix 5: Load model + move to device
    device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processor = LayoutLMv3Processor.from_pretrained(model_dir, apply_ocr=False)
    model     = LayoutLMv3ForTokenClassification.from_pretrained(model_dir)
    model.to(device)       # Fix 5
    model.eval()

    test_dataset = GSTInvoiceDataset(test_image_dir, test_ann_dir, processor, max_length)

    all_predictions, all_labels = [], []

    for i in range(len(test_dataset)):
        sample    = test_dataset[i]
        inputs    = {k: v.unsqueeze(0) for k, v in sample.items() if k != "labels"}
        label_ids = sample["labels"].tolist()

        # Fix 5: Move inputs to device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)

        preds = outputs.logits.argmax(-1).squeeze().tolist()

        pred_row, label_row = [], []
        for p, l in zip(preds, label_ids):
            if l == -100:
                continue
            pred_row.append(ID2LABEL.get(p, "O"))
            label_row.append(ID2LABEL.get(l, "O"))

        all_predictions.append(pred_row)
        all_labels.append(label_row)

    results = seqeval.compute(predictions=all_predictions, references=all_labels)

    print(f"\n Test Results:")
    print(f"   F1        : {results['overall_f1']:.4f}")
    print(f"   Precision : {results['overall_precision']:.4f}")
    print(f"   Recall    : {results['overall_recall']:.4f}")
    print(f"   Accuracy  : {results['overall_accuracy']:.4f}")

    print(f"\n Per-Field Results:")
    for field, metrics in results.items():
        if isinstance(metrics, dict):
            print(
                f"   {field:<22} → "
                f"F1: {metrics['f1']:.4f}  "
                f"P: {metrics['precision']:.4f}  "
                f"R: {metrics['recall']:.4f}"
            )

    return results


evaluate_test_set(
    test_image_dir = "/content/drive/MyDrive/TScript/test/images",
    test_ann_dir   = "/content/drive/MyDrive/TScript/test/annotations",
    model_dir      = "/content/drive/MyDrive/model",
)

import os
import json

# ── Paths ──────────────────────────────────────────────────────────────────────
ann_dir = "/content/drive/MyDrive/TScript/test/annotations"
img_dir = "/content/drive/MyDrive/TScript/test/images"

# ── Helper: match annotation to image file ─────────────────────────────────────
def find_image_path(ann_image_val, img_dir):
    """
    Match ann['image'] (possibly a Windows path) to an actual file in img_dir.
    Matches by stem so extension differences are handled too.
    """
    ann_stem = ann_image_val.replace("\\", "/").split("/")[-1].rsplit(".", 1)[0]

    for fname in os.listdir(img_dir):
        if fname.rsplit(".", 1)[0] == ann_stem:
            return os.path.join(img_dir, fname)

    raise FileNotFoundError(
        f"No image matching stem '{ann_stem}' found in {img_dir}"
    )

# ── Main loop ──────────────────────────────────────────────────────────────────
ann_files = sorted(f for f in os.listdir(ann_dir) if f.endswith(".json"))

print(f"Found {len(ann_files)} annotation files\n")

all_results = {}

for ann_file in ann_files:
    ann_path = os.path.join(ann_dir, ann_file)

    try:
        # 1. Load annotation
        with open(ann_path, "r") as f:
            ann = json.load(f)

        # 2. Extract words and bboxes (skip empty tokens)
        words  = [w["text"] for w in ann["layout"]["words"] if w["text"].strip()]
        bboxes = [w["bbox"] for w in ann["layout"]["words"] if w["text"].strip()]

        # 3. Resolve image path via ann["image"] stem matching
        image_path = find_image_path(ann["image"], img_dir)

        # 4. Run NER extraction
        fields = extract_fields(
            image_path,
            words,
            bboxes,
            model=inference_model,
            processor=inference_processor
        )

        all_results[ann_file] = {
            "image": image_path,
            "fields": fields
        }

        print(f" {ann_file}")
        print(f"   Image : {os.path.basename(image_path)}")
        print(f"   Fields: {fields}\n")

    except FileNotFoundError as e:
        print(f"  SKIP {ann_file} — {e}\n")

    except Exception as e:
        print(f" ERROR in {ann_file} — {e}\n")

# ── Summary ────────────────────────────────────────────────────────────────────
print(f"Done. Processed {len(all_results)} / {len(ann_files)} files successfully.")
