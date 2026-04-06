"""
model.py  –  LayoutLMv3 Token Classification Model
====================================================
Defines and loads the LayoutLMv3ForTokenClassification model
for GST Invoice field extraction.

Fields extracted:
    INVOICE_NO | INVOICE_DATE | GSTIN | TOTAL_AMOUNT |
    GST_AMOUNT | TAXABLE_AMOUNT | MERCHANT

Usage:
    from model import LABELS, label2id, id2label, load_model, load_processor
"""

from transformers import (
    LayoutLMv3ForTokenClassification,
    LayoutLMv3Processor,
)


# ─────────────────────────────────────────
# LABEL SCHEMA
# ─────────────────────────────────────────

LABELS = [
    "O",
    "B-INVOICE_NO",
    "B-INVOICE_DATE",
    "B-GSTIN",
    "B-TOTAL_AMOUNT",
    "B-GST_AMOUNT",
    "B-TAXABLE_AMOUNT",
    "B-MERCHANT",
]

label2id = {label: idx for idx, label in enumerate(LABELS)}
id2label = {idx: label for label, idx in label2id.items()}

NUM_LABELS = len(LABELS)

BASE_MODEL = "microsoft/layoutlmv3-base"


# ─────────────────────────────────────────
# LOADER FUNCTIONS
# ─────────────────────────────────────────

def load_model(checkpoint_path=None):
    """
    Load LayoutLMv3ForTokenClassification.

    Args:
        checkpoint_path (str, optional):
            Path to a fine-tuned model directory (e.g. './model').
            If None, loads the base pretrained weights — use for training.

    Returns:
        LayoutLMv3ForTokenClassification
    """
    source = checkpoint_path if checkpoint_path else BASE_MODEL

    model = LayoutLMv3ForTokenClassification.from_pretrained(
        source,
        num_labels=NUM_LABELS,
        id2label=id2label,
        label2id=label2id,
        ignore_mismatched_sizes=True,   # safe when loading base weights
    )
    return model


def load_processor(checkpoint_path=None):
    """
    Load LayoutLMv3Processor with OCR disabled
    (OCR is handled externally by Tesseract / EasyOCR).

    Args:
        checkpoint_path (str, optional):
            Path to a saved processor directory.
            If None, loads from the base HuggingFace model.

    Returns:
        LayoutLMv3Processor
    """
    source = checkpoint_path if checkpoint_path else BASE_MODEL

    processor = LayoutLMv3Processor.from_pretrained(
        source,
        apply_ocr=False,
    )
    return processor


# ─────────────────────────────────────────
# QUICK SANITY CHECK
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("Loading processor ...")
    processor = load_processor()
    print(f"  Processor : {processor.__class__.__name__}")

    print("\nLoading model (base weights) ...")
    model = load_model()
    print(f"  Model     : {model.__class__.__name__}")
    print(f"  Labels    : {NUM_LABELS}")
    for idx, label in id2label.items():
        print(f"    {idx:>2}  {label}")

    total_params = sum(p.numel() for p in model.parameters())
    trainable    = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n  Total params    : {total_params:,}")
    print(f"  Trainable params: {trainable:,}")
    print("\n model.py OK")
