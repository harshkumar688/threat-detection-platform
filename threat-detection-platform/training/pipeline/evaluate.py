"""
Model Evaluation

Runs evaluation on the test (or val) split and reports:
- mAP@0.5, mAP@0.5:0.95
- Per-class Precision, Recall, F1
- Confusion matrix
- Detection counts

All metrics come from actual model inference — nothing is fabricated.

Usage:
    python -m pipeline.evaluate --model runs/experiment/weights/best.pt --data datasets/weapon_detection/data.yaml
    python -m pipeline.evaluate --model runs/experiment/weights/best.pt --data datasets/weapon_detection/data.yaml --split test
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import yaml


def evaluate_model(
    model_path: str,
    data_yaml: str,
    split: str = "val",
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.5,
    device: str = "auto",
    output_dir: Optional[str] = None,
    imgsz: int = 640,
) -> Dict:
    """
    Evaluate a trained model and return metrics.

    Args:
        model_path: Path to .pt model weights.
        data_yaml: Path to data.yaml dataset config.
        split: Which split to evaluate ("val" or "test").
        conf_threshold: Confidence threshold for predictions.
        iou_threshold: IoU threshold for mAP calculation.
        device: Compute device.
        output_dir: Directory to save results. If None, uses model parent.
        imgsz: Inference input size.

    Returns:
        Dictionary containing all computed metrics.
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ERROR: ultralytics not installed")
        sys.exit(1)

    # Validate inputs
    if not Path(model_path).exists():
        print(f"ERROR: Model not found: {model_path}")
        sys.exit(1)

    if not Path(data_yaml).exists():
        print(f"ERROR: Dataset config not found: {data_yaml}")
        sys.exit(1)

    # Resolve device
    if device == "auto":
        import torch
        device = "0" if torch.cuda.is_available() else "cpu"

    # Load model
    print(f"\nLoading model: {model_path}")
    model = YOLO(model_path)

    # Run validation
    print(f"Evaluating on '{split}' split...")
    print(f"  Confidence threshold: {conf_threshold}")
    print(f"  IoU threshold: {iou_threshold}")
    print(f"  Image size: {imgsz}")
    print(f"  Device: {device}")
    print()

    start_time = time.time()

    results = model.val(
        data=data_yaml,
        split=split,
        conf=conf_threshold,
        iou=iou_threshold,
        device=device,
        imgsz=imgsz,
        plots=True,
        save_json=True,
    )

    eval_duration = time.time() - start_time

    # Extract metrics from results
    metrics = _extract_metrics(results, eval_duration, model_path, data_yaml, split)

    # Save results
    if output_dir:
        save_dir = Path(output_dir)
    else:
        save_dir = Path(model_path).parent.parent / "evaluation"
    save_dir.mkdir(parents=True, exist_ok=True)

    results_path = save_dir / f"eval_results_{split}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    print(f"\nResults saved to: {results_path}")

    return metrics


def _extract_metrics(results, duration: float, model_path: str, data_yaml: str, split: str) -> Dict:
    """Extract metrics from Ultralytics validation results."""
    # results.box contains box metrics
    box = results.box

    metrics = {
        "metadata": {
            "model": model_path,
            "dataset": data_yaml,
            "split": split,
            "timestamp": datetime.now().isoformat(),
            "eval_duration_seconds": round(duration, 2),
        },
        "summary": {
            "mAP50": float(box.map50),
            "mAP50_95": float(box.map),
            "precision": float(box.mp),
            "recall": float(box.mr),
            "f1": _compute_f1(float(box.mp), float(box.mr)),
        },
        "per_class": {},
    }

    # Per-class metrics
    if hasattr(box, "ap_class_index") and box.ap_class_index is not None:
        class_names = results.names
        for i, class_idx in enumerate(box.ap_class_index):
            name = class_names.get(int(class_idx), f"class_{class_idx}")
            metrics["per_class"][name] = {
                "precision": float(box.p[i]),
                "recall": float(box.r[i]),
                "f1": _compute_f1(float(box.p[i]), float(box.r[i])),
                "ap50": float(box.ap50[i]),
                "ap50_95": float(box.ap[i]),
            }

    return metrics


def _compute_f1(precision: float, recall: float) -> float:
    """Compute F1 score from precision and recall."""
    if precision + recall == 0:
        return 0.0
    return round(2 * (precision * recall) / (precision + recall), 4)


def print_metrics_report(metrics: Dict) -> None:
    """Print a formatted evaluation report."""
    from tabulate import tabulate

    print("\n" + "=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    meta = metrics["metadata"]
    print(f"\n  Model:    {meta['model']}")
    print(f"  Dataset:  {meta['dataset']}")
    print(f"  Split:    {meta['split']}")
    print(f"  Duration: {meta['eval_duration_seconds']:.1f}s")

    summary = metrics["summary"]
    print(f"\n--- Overall Metrics ---")
    print(f"  mAP@0.5:       {summary['mAP50']:.4f}")
    print(f"  mAP@0.5:0.95:  {summary['mAP50_95']:.4f}")
    print(f"  Precision:      {summary['precision']:.4f}")
    print(f"  Recall:         {summary['recall']:.4f}")
    print(f"  F1 Score:       {summary['f1']:.4f}")

    if metrics["per_class"]:
        print(f"\n--- Per-Class Metrics ---")
        table = []
        for name, cls_metrics in metrics["per_class"].items():
            table.append([
                name,
                f"{cls_metrics['precision']:.4f}",
                f"{cls_metrics['recall']:.4f}",
                f"{cls_metrics['f1']:.4f}",
                f"{cls_metrics['ap50']:.4f}",
                f"{cls_metrics['ap50_95']:.4f}",
            ])

        print(tabulate(
            table,
            headers=["Class", "Precision", "Recall", "F1", "AP@0.5", "AP@0.5:0.95"],
            tablefmt="grid",
        ))

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained YOLO model")
    parser.add_argument("--model", type=str, required=True, help="Path to model weights (.pt)")
    parser.add_argument("--data", type=str, required=True, help="Path to data.yaml")
    parser.add_argument("--split", type=str, default="val", choices=["val", "test"])
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.5, help="IoU threshold for mAP")
    parser.add_argument("--device", type=str, default="auto", help="Device (auto, cpu, 0)")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    metrics = evaluate_model(
        model_path=args.model,
        data_yaml=args.data,
        split=args.split,
        conf_threshold=args.conf,
        iou_threshold=args.iou,
        device=args.device,
        output_dir=args.output_dir,
        imgsz=args.imgsz,
    )

    print_metrics_report(metrics)


if __name__ == "__main__":
    main()
