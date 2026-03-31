"""
model.py — LayoutLMv3 Model Manager for GST Invoice Field Extraction
---------------------------------------------------------------------
Handles: model loading, config, checkpoint save/load, and pipeline interface.

Usage:
    from model import InvoiceLayoutModel

    # Load for training
    model_manager = InvoiceLayoutModel()
    model, processor = model_manager.load_for_training()

    # Load for inference (after fine-tuning)
    model_manager = InvoiceLayoutModel(model_dir="models/layoutlmv3-gst-invoices")
    model, processor = model_manager.load_for_inference()
"""

import os
import json
import torch
from pathlib import Path
from transformers import (
    LayoutLMv3ForTokenClassification,
    LayoutLMv3Processor,
    LayoutLMv3Config,
)

# 1.  LABEL CONFIGURATION

# All GST invoice field types
FIELD_TYPES = [
    "GSTIN",
    "SELLER_NAME",
    "BUYER_NAME",
    "INVOICE_NO",
    "INVOICE_DATE",
    "HSN_CODE",
    "TAXABLE_AMT",
    "CGST",
    "SGST",
    "IGST",
    "TOTAL_AMT",
    "ITEM_DESC",
]

# BIO label scheme
LABEL_LIST = ["O"]
for field in FIELD_TYPES:
    LABEL_LIST.append(f"B-{field}")
    LABEL_LIST.append(f"I-{field}")

LABEL2ID = {label: idx for idx, label in enumerate(LABEL_LIST)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}


# 2.  MODEL MANAGER CLASS

class InvoiceLayoutModel:
    """
    Manages LayoutLMv3 model lifecycle:
      - Load pretrained base model for fine-tuning
      - Load fine-tuned checkpoint for inference
      - Save and restore checkpoints
      - Expose model info and device management
    """

    BASE_MODEL = "microsoft/layoutlmv3-base"

    def __init__(self, model_dir: str = "models/layoutlmv3-gst-invoices"):
        self.model_dir = Path(model_dir)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model     = None
        self.processor = None
        print(f" Device: {self.device}")
        print(f" Model dir: {self.model_dir}")

    # ── Internal helpers ──────────────────────

    def _build_processor(self, source: str) -> LayoutLMv3Processor:
        """Load processor with apply_ocr=False (we supply Tesseract output)."""
        return LayoutLMv3Processor.from_pretrained(source, apply_ocr=False)

    def _build_model(self, source: str) -> LayoutLMv3ForTokenClassification:
        """Load model with our label configuration."""
        return LayoutLMv3ForTokenClassification.from_pretrained(
            source,
            num_labels=len(LABEL_LIST),
            id2label=ID2LABEL,
            label2id=LABEL2ID,
            ignore_mismatched_sizes=True,   # needed when loading base → custom labels
        )

    # ── Public API ────────────────────────────

    def load_for_training(self):
        """
        Load the base LayoutLMv3 pretrained model for fine-tuning.
        Always starts from microsoft/layoutlmv3-base.

        Returns:
            (model, processor) ready for HuggingFace Trainer
        """
        print(f"\n Loading base model: {self.BASE_MODEL}")
        self.processor = self._build_processor(self.BASE_MODEL)
        self.model     = self._build_model(self.BASE_MODEL)
        self.model.to(self.device)
        self._print_model_info()
        return self.model, self.processor

    def load_for_inference(self):
        """
        Load a previously fine-tuned model from model_dir for inference.

        Returns:
            (model, processor) in eval mode
        """
        if not self.model_dir.exists():
            raise FileNotFoundError(
                f" Fine-tuned model not found at: {self.model_dir}\n"
                f"   Run training first using layoutlmv3_finetune.py"
            )
        print(f"\n Loading fine-tuned model from: {self.model_dir}")
        self.processor = self._build_processor(str(self.model_dir))
        self.model     = LayoutLMv3ForTokenClassification.from_pretrained(
            str(self.model_dir)
        )
        self.model.to(self.device)
        self.model.eval()
        print(" Model loaded in eval mode.")
        return self.model, self.processor

    def save(self, save_dir: str = None):
        """
        Save model + processor to disk.

        Args:
            save_dir: directory to save (defaults to self.model_dir)
        """
        if self.model is None or self.processor is None:
            raise RuntimeError(" No model loaded. Call load_for_training() first.")

        target = Path(save_dir) if save_dir else self.model_dir
        target.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(str(target))
        self.processor.save_pretrained(str(target))

        # Save label config for reference
        label_config = {
            "label_list": LABEL_LIST,
            "label2id":   LABEL2ID,
            "id2label":   {str(k): v for k, v in ID2LABEL.items()},
            "num_labels": len(LABEL_LIST),
        }
        with open(target / "label_config.json", "w") as f:
            json.dump(label_config, f, indent=2)

        print(f" Model saved to: {target}")

    def load_checkpoint(self, checkpoint_path: str):
        """
        Load a specific training checkpoint (e.g. checkpoint-500).

        Args:
            checkpoint_path: path to checkpoint folder
        """
        print(f"\n Loading checkpoint: {checkpoint_path}")
        self.processor = self._build_processor(checkpoint_path)
        self.model     = LayoutLMv3ForTokenClassification.from_pretrained(checkpoint_path)
        self.model.to(self.device)
        return self.model, self.processor

    def get_model_config(self) -> dict:
        """Return model configuration as a dict."""
        if self.model is None:
            raise RuntimeError("No model loaded.")
        cfg = self.model.config
        return {
            "model_type":       cfg.model_type,
            "hidden_size":      cfg.hidden_size,
            "num_layers":       cfg.num_hidden_layers,
            "num_attention_heads": cfg.num_attention_heads,
            "num_labels":       cfg.num_labels,
            "id2label":         cfg.id2label,
            "max_position_embeddings": cfg.max_position_embeddings,
        }

    def count_parameters(self) -> dict:
        """Count total and trainable parameters."""
        if self.model is None:
            raise RuntimeError("No model loaded.")
        total     = sum(p.numel() for p in self.model.parameters())
        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        return {
            "total_parameters":     total,
            "trainable_parameters": trainable,
            "frozen_parameters":    total - trainable,
        }

    def freeze_backbone(self):
        """
        Freeze the LayoutLMv3 backbone, train only the classification head.
        Useful when you have very little labeled data (<100 samples).
        """
        if self.model is None:
            raise RuntimeError("No model loaded.")
        for name, param in self.model.named_parameters():
            if "classifier" not in name:
                param.requires_grad = False
        params = self.count_parameters()
        print(f" Backbone frozen. Trainable params: {params['trainable_parameters']:,}")

    def unfreeze_all(self):
        """Unfreeze all parameters for full fine-tuning."""
        if self.model is None:
            raise RuntimeError("No model loaded.")
        for param in self.model.parameters():
            param.requires_grad = True
        params = self.count_parameters()
        print(f" All layers unfrozen. Trainable params: {params['trainable_parameters']:,}")

    def _print_model_info(self):
        """Print a summary of the loaded model."""
        params = self.count_parameters()
        print(f"\n{'─'*45}")
        print(f"  Model       : {self.BASE_MODEL}")
        print(f"  Labels      : {len(LABEL_LIST)}  → {LABEL_LIST[:5]}...")
        print(f"  Total params: {params['total_parameters']:,}")
        print(f"  Trainable   : {params['trainable_parameters']:,}")
        print(f"  Device      : {self.device}")
        print(f"{'─'*45}\n")

# 3.  CONVENIENCE FUNCTIONS


def get_label_list() -> list:
    """Return the full BIO label list."""
    return LABEL_LIST

def get_label_maps() -> tuple:
    """Return (label2id, id2label) dicts."""
    return LABEL2ID, ID2LABEL

def get_num_labels() -> int:
    """Return total number of labels."""
    return len(LABEL_LIST)

# 4.  QUICK TEST

if __name__ == "__main__":
    print("=== InvoiceLayoutModel — Quick Test ===\n")

    # Test 1: Load for training
    manager = InvoiceLayoutModel()
    model, processor = manager.load_for_training()

    # Test 2: Model config
    config = manager.get_model_config()
    print("Model config:", json.dumps(config, indent=2, default=str))

    # Test 3: Parameter count
    params = manager.count_parameters()
    print(f"\nParameters: {params}")

    # Test 4: Freeze backbone (useful for small datasets)
    manager.freeze_backbone()

    # Test 5: Unfreeze for full fine-tuning
    manager.unfreeze_all()

    # Test 6: Save
    manager.save("models/layoutlmv3-gst-invoices-test")

    print("\n All tests passed.")
