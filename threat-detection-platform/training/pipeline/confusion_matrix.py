"""
Confusion Matrix Generation

Generates and saves a confusion matrix from model predictions vs ground truth.
Operates on the validation or test split using actual model inference.

Usage:
    python -m pipeline.confusion_matrix --model runs/experiment/weights/best.pt --data datasets/weapon_detection/data.yaml
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


def generate_confusion_matrix(
    model_path: str,
    data_yaml: str,
    split: str = "val",
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.5,
    device: str = "auto",
    output_dir: Optional[str] = None,
    imgsz: int = 640,
    normalize: bool = True,
) -> Dict:
    """
    Generate confusion matrix from model predictions.

    Uses Ultralytics built-in confusion matrix generation during validation,
    then extracts and formats the results.

    Args:
        model_path: Path to trained model weights.
        data_yaml: Path to data.yaml.
        split: Dataset split to use.
        conf_threshold: Confidence threshold.
        iou_threshold: IoU threshold for matching.
        device: Compute device.
        output_dir: Where to save the matrix plot.
        imgsz: Input image size.
        normalize: Whether to normalize the matrix.

    Returns:
        Dictionary with confusion matrix data and derived metrics.
    """
    try:
        from ultralytics import YOLO
        import torch
    except ImportError:
        print("ERROR: ultralytics not installed")
        sys.exit(1)

    if not Path(model_path).exists():
        print(f"ERROR: Model not found: {model_path}")
        sys.exit(1)

    # Resolve device
    if device == "auto":
        device = "0" if torch.cuda.is_available() else "cpu"

    # Load and validate
    model = YOLO(model_path)

    print(f"\nGenerating confusion matrix...")
    print(f"  Model:  {model_path}")
    print(f"  Split:  {split}")
    print(f"  Conf:   {conf_threshold}")
    print(f"  IoU:    {iou_threshold}")

    # Run validation (generates confusion matrix internally)
    results = model.val(
        data=data_yaml,
        split=split,
        conf=conf_threshold,
        iou=iou_threshold,
        device=device,
        imgsz=imgsz,
        plots=True,  # This generates confusion_matrix.png
        verbose=False,
    )

    # Extract confusion matrix from results
    cm = results.confusion_matrix
    matrix = cm.matrix  # numpy array (nc+1 x nc+1), last row/col is background

    class_names = list(results.names.values())

    # Compute per-class metrics from confusion matrix
    per_class_metrics = _compute_per_class_from_matrix(matrix, class_names)

    # Determine output path
    if output_dir:
        save_dir = Path(output_dir)
    else:
        save_dir = Path(model_path).parent.parent / "evaluation"
    save_dir.mkdir(parents=True, exist_ok=True)

    # Generate custom plot
    _plot_confusion_matrix(
        matrix=matrix,
        class_names=class_names + ["background"],
        output_path=save_dir / "confusion_matrix.png",
        normalize=normalize,
    )

    result_data = {
        "matrix": matrix.tolist(),
        "class_names": class_names,
        "per_class_metrics": per_class_metrics,
        "output_path": str(save_dir / "confusion_matrix.png"),
    }

    print(f"\n  Confusion matrix saved to: {save_dir / 'confusion_matrix.png'}")
    _print_per_class_table(per_class_metrics)

    return result_data


def _compute_per_class_from_matrix(matrix: np.ndarray, class_names: List[str]) -> Dict:
    """
    Compute per-class TP, FP, FN, Precision, Recall, F1 from confusion matrix.

    The matrix shape is (nc+1, nc+1) where last index is background/no-detection.
    Rows = ground truth, Cols = predictions.
    """
    nc = len(class_names)
    metrics = {}

    for i, name in enumerate(class_names):
        tp = matrix[i, i]
        fp = matrix[:, i].sum() - tp  # All predicted as this class, minus correct
        fn = matrix[i, :].sum() - tp  # All actually this class, minus correct

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics[name] = {
            "true_positives": int(tp),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    return metrics


def _plot_confusion_matrix(
    matrix: np.ndarray,
    class_names: List[str],
    output_path: Path,
    normalize: bool = True,
) -> None:
    """Generate and save confusion matrix heatmap."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        print("  WARNING: matplotlib/seaborn not installed, skipping plot generation")
        return

    if normalize:
        # Normalize by row (ground truth)
        row_sums = matrix.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1  # Avoid division by zero
        plot_matrix = matrix / row_sums
        fmt = ".2f"
        title = "Confusion Matrix (Normalized)"
    else:
        plot_matrix = matrix
        fmt = "g"
        title = "Confusion Matrix"

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        plot_matrix,
        annot=True,
        fmt=fmt,
        cmap="Blues",
        xticklabels=class_names,
        yticklabels=class_names,
        ax=ax,
        square=True,
        cbar_kws={"shrink": 0.8},
    )
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("Actual", fontsize=12)
    ax.set_title(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def _print_per_class_table(per_class_metrics: Dict) -> None:
    """Print per-class metrics table."""
    try:
        from tabulate import tabulate
    except ImportError:
        return

    table = []
    for name, m in per_class_metrics.items():
        table.append([
            name,
            m["true_positives"],
            m["false_positives"],
            m["false_negatives"],
            f"{m['precision']:.4f}",
            f"{m['recall']:.4f}",
            f"{m['f1']:.4f}",
        ])

    print("\n  --- Per-Class Metrics (from Confusion Matrix) ---")
    print(tabulate(
        table,
        headers=["Class", "TP", "FP", "FN", "Precision", "Recall", "F1"],
        tablefmt="grid",
    ))


def main():
    parser = argparse.ArgumentParser(description="Generate confusion matrix")
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--data", type=str, required=True)
    parser.add_argument("--split", type=str, default="val", choices=["val", "test"])
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()

    generate_confusion_matrix(
        model_path=args.model,
        data_yaml=args.data,
        split=args.split,
        conf_threshold=args.conf,
        iou_threshold=args.iou,
        device=args.device,
        output_dir=args.output_dir,
        imgsz=args.imgsz,
        normalize=not args.no_normalize,
    )


if __name__ == "__main__":
    main()
