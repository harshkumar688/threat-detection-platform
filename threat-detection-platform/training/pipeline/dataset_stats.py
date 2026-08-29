"""
Dataset Statistics

Computes and reports detailed dataset statistics:
- Per-class instance counts
- Per-split distributions
- Image resolution statistics
- Bounding box size distributions
- Class balance analysis

Usage:
    python -m pipeline.dataset_stats --data-dir datasets/weapon_detection
"""

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
from tabulate import tabulate

from .dataset_config import DatasetConfig


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def compute_dataset_stats(data_dir: Path) -> Dict:
    """
    Compute comprehensive dataset statistics.

    Args:
        data_dir: Root dataset directory containing data.yaml.

    Returns:
        Dictionary with all computed statistics.
    """
    yaml_path = data_dir / "data.yaml"
    config = DatasetConfig.from_yaml(yaml_path)

    stats = {
        "dataset_path": str(data_dir),
        "num_classes": config.nc,
        "class_names": config.class_names,
        "splits": {},
        "totals": {
            "images": 0,
            "annotations": 0,
            "class_counts": Counter(),
        },
    }

    splits = [
        ("train", config.train_images_path, config.train_labels_path),
        ("val", config.val_images_path, config.val_labels_path),
    ]
    if config.test_images_path and config.test_images_path.exists():
        splits.append(("test", config.test_images_path, config.test_labels_path))

    for split_name, images_dir, labels_dir in splits:
        if not images_dir.exists() or not labels_dir.exists():
            continue

        split_stats = _compute_split_stats(images_dir, labels_dir, config)
        stats["splits"][split_name] = split_stats
        stats["totals"]["images"] += split_stats["num_images"]
        stats["totals"]["annotations"] += split_stats["num_annotations"]
        stats["totals"]["class_counts"] += Counter(split_stats["class_counts"])

    return stats


def _compute_split_stats(
    images_dir: Path,
    labels_dir: Path,
    config: DatasetConfig,
) -> Dict:
    """Compute statistics for a single split."""
    image_files = [
        f for f in images_dir.iterdir()
        if f.suffix.lower() in IMAGE_EXTENSIONS
    ]
    label_files = [
        f for f in labels_dir.iterdir()
        if f.suffix == ".txt"
    ]

    # Parse all annotations
    class_counts = Counter()
    bbox_widths = []
    bbox_heights = []
    bbox_areas = []
    annotations_per_image = []
    total_annotations = 0

    for label_path in label_files:
        with open(label_path) as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        annotations_per_image.append(len(lines))

        for line in lines:
            parts = line.split()
            if len(parts) != 5:
                continue

            class_id = int(parts[0])
            w = float(parts[3])
            h = float(parts[4])

            class_counts[class_id] += 1
            bbox_widths.append(w)
            bbox_heights.append(h)
            bbox_areas.append(w * h)
            total_annotations += 1

    # Image resolution sampling (check first 50 images)
    widths = []
    heights = []
    for img_path in image_files[:50]:
        img = cv2.imread(str(img_path))
        if img is not None:
            h, w = img.shape[:2]
            widths.append(w)
            heights.append(h)

    # Build named class counts
    named_class_counts = {}
    for class_id, count in sorted(class_counts.items()):
        name = config.names.get(class_id, f"class_{class_id}")
        named_class_counts[name] = count

    return {
        "num_images": len(image_files),
        "num_labels": len(label_files),
        "num_annotations": total_annotations,
        "class_counts": named_class_counts,
        "annotations_per_image": {
            "mean": float(np.mean(annotations_per_image)) if annotations_per_image else 0,
            "median": float(np.median(annotations_per_image)) if annotations_per_image else 0,
            "max": max(annotations_per_image) if annotations_per_image else 0,
            "min": min(annotations_per_image) if annotations_per_image else 0,
        },
        "bbox_stats": {
            "width_mean": float(np.mean(bbox_widths)) if bbox_widths else 0,
            "height_mean": float(np.mean(bbox_heights)) if bbox_heights else 0,
            "area_mean": float(np.mean(bbox_areas)) if bbox_areas else 0,
            "width_std": float(np.std(bbox_widths)) if bbox_widths else 0,
            "height_std": float(np.std(bbox_heights)) if bbox_heights else 0,
        },
        "image_resolution": {
            "width_mean": int(np.mean(widths)) if widths else 0,
            "height_mean": int(np.mean(heights)) if heights else 0,
            "width_range": (min(widths), max(widths)) if widths else (0, 0),
            "height_range": (min(heights), max(heights)) if heights else (0, 0),
        },
    }


def print_stats_report(stats: Dict) -> None:
    """Print formatted statistics report."""
    print("\n" + "=" * 70)
    print("DATASET STATISTICS REPORT")
    print("=" * 70)
    print(f"\nDataset: {stats['dataset_path']}")
    print(f"Classes: {stats['num_classes']} — {stats['class_names']}")
    print(f"Total images: {stats['totals']['images']}")
    print(f"Total annotations: {stats['totals']['annotations']}")

    # Per-split table
    print("\n--- Split Summary ---")
    split_table = []
    for split_name, split_data in stats["splits"].items():
        split_table.append([
            split_name,
            split_data["num_images"],
            split_data["num_annotations"],
            f"{split_data['annotations_per_image']['mean']:.1f}",
        ])

    print(tabulate(
        split_table,
        headers=["Split", "Images", "Annotations", "Avg Ann/Image"],
        tablefmt="grid",
    ))

    # Per-class table
    print("\n--- Class Distribution (Total) ---")
    class_table = []
    total = stats["totals"]["annotations"]
    for name, count in sorted(stats["totals"]["class_counts"].items(), key=lambda x: -x[1]):
        pct = (count / total * 100) if total > 0 else 0
        class_table.append([name, count, f"{pct:.1f}%"])

    print(tabulate(
        class_table,
        headers=["Class", "Count", "Percentage"],
        tablefmt="grid",
    ))

    # Bbox stats from first split
    if stats["splits"]:
        first_split = list(stats["splits"].values())[0]
        bbox = first_split["bbox_stats"]
        print("\n--- Bounding Box Statistics (train) ---")
        print(f"  Mean width:  {bbox['width_mean']:.4f} (std: {bbox['width_std']:.4f})")
        print(f"  Mean height: {bbox['height_mean']:.4f} (std: {bbox['height_std']:.4f})")
        print(f"  Mean area:   {bbox['area_mean']:.6f}")

        res = first_split["image_resolution"]
        print(f"\n--- Image Resolution ---")
        print(f"  Mean: {res['width_mean']}x{res['height_mean']}")
        print(f"  Width range:  {res['width_range']}")
        print(f"  Height range: {res['height_range']}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Compute dataset statistics")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to dataset root")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not (data_dir / "data.yaml").exists():
        print(f"ERROR: data.yaml not found in {data_dir}")
        sys.exit(1)

    stats = compute_dataset_stats(data_dir)
    print_stats_report(stats)


if __name__ == "__main__":
    main()
