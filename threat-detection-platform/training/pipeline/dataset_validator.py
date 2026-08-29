"""
Dataset Validator

Validates dataset integrity before training:
- Directory structure exists
- Images are readable
- Labels follow YOLO format
- Class IDs are within range
- Bounding box coordinates are valid (0-1)
- Image/label pairing (no orphans)
- Train/val/test splits exist

Usage:
    python -m pipeline.dataset_validator --data-dir datasets/weapon_detection
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple

import cv2

from .dataset_config import DatasetConfig


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


@dataclass
class ValidationResult:
    """Result of dataset validation."""

    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def print_report(self):
        """Print validation report to console."""
        print("\n" + "=" * 60)
        print("DATASET VALIDATION REPORT")
        print("=" * 60)

        if self.is_valid:
            print("\n✅ Dataset is VALID\n")
        else:
            print("\n❌ Dataset has ERRORS\n")

        if self.errors:
            print(f"ERRORS ({len(self.errors)}):")
            for err in self.errors:
                print(f"  ❌ {err}")
            print()

        if self.warnings:
            print(f"WARNINGS ({len(self.warnings)}):")
            for warn in self.warnings:
                print(f"  ⚠️  {warn}")
            print()

        if self.stats:
            print("STATISTICS:")
            for key, val in self.stats.items():
                print(f"  {key}: {val}")
            print()

        print("=" * 60)


def validate_dataset(data_dir: Path) -> ValidationResult:
    """
    Validate a complete dataset directory.

    Args:
        data_dir: Root path to the dataset (contains data.yaml).

    Returns:
        ValidationResult with errors, warnings, and stats.
    """
    result = ValidationResult()

    # --- Check data.yaml ---
    yaml_path = data_dir / "data.yaml"
    if not yaml_path.exists():
        result.add_error(f"data.yaml not found at: {yaml_path}")
        return result

    try:
        config = DatasetConfig.from_yaml(yaml_path)
    except Exception as e:
        result.add_error(f"Invalid data.yaml: {e}")
        return result

    result.stats["classes"] = config.class_names
    result.stats["num_classes"] = config.nc

    # --- Validate splits ---
    splits = [("train", config.train_images_path, config.train_labels_path)]
    splits.append(("val", config.val_images_path, config.val_labels_path))
    if config.test_images_path:
        splits.append(("test", config.test_images_path, config.test_labels_path))

    total_images = 0
    total_labels = 0
    total_annotations = 0

    for split_name, images_dir, labels_dir in splits:
        if not images_dir.exists():
            result.add_error(f"[{split_name}] Images directory not found: {images_dir}")
            continue

        if not labels_dir.exists():
            result.add_error(f"[{split_name}] Labels directory not found: {labels_dir}")
            continue

        # Get image and label files
        image_files = {
            f.stem: f for f in images_dir.iterdir()
            if f.suffix.lower() in IMAGE_EXTENSIONS
        }
        label_files = {
            f.stem: f for f in labels_dir.iterdir()
            if f.suffix == ".txt"
        }

        split_images = len(image_files)
        split_labels = len(label_files)
        total_images += split_images
        total_labels += split_labels

        result.stats[f"{split_name}_images"] = split_images
        result.stats[f"{split_name}_labels"] = split_labels

        if split_images == 0:
            result.add_error(f"[{split_name}] No images found in {images_dir}")
            continue

        # Check for orphans
        images_without_labels = set(image_files.keys()) - set(label_files.keys())
        labels_without_images = set(label_files.keys()) - set(image_files.keys())

        if images_without_labels:
            count = len(images_without_labels)
            if count > 10:
                result.add_warning(
                    f"[{split_name}] {count} images have no matching label file"
                )
            else:
                for name in list(images_without_labels)[:5]:
                    result.add_warning(f"[{split_name}] No label for image: {name}")

        if labels_without_images:
            count = len(labels_without_images)
            result.add_warning(f"[{split_name}] {count} labels have no matching image")

        # Validate annotations
        annotation_count, annotation_errors = _validate_annotations(
            labels_dir, label_files, config.nc, split_name
        )
        total_annotations += annotation_count

        for err in annotation_errors[:20]:  # Limit reported errors
            result.add_error(err)

        if len(annotation_errors) > 20:
            result.add_error(
                f"[{split_name}] ... and {len(annotation_errors) - 20} more annotation errors"
            )

        # Spot-check a few images are readable
        check_count = min(5, split_images)
        for stem in list(image_files.keys())[:check_count]:
            img = cv2.imread(str(image_files[stem]))
            if img is None:
                result.add_error(f"[{split_name}] Cannot read image: {image_files[stem].name}")

    result.stats["total_images"] = total_images
    result.stats["total_labels"] = total_labels
    result.stats["total_annotations"] = total_annotations

    return result


def _validate_annotations(
    labels_dir: Path,
    label_files: dict,
    num_classes: int,
    split_name: str,
) -> Tuple[int, List[str]]:
    """
    Validate all annotation files in a split.

    Returns:
        (total_annotation_count, list_of_errors)
    """
    errors = []
    total_annotations = 0

    for stem, label_path in label_files.items():
        try:
            with open(label_path) as f:
                lines = f.readlines()
        except Exception as e:
            errors.append(f"[{split_name}] Cannot read label: {label_path.name}: {e}")
            continue

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) != 5:
                errors.append(
                    f"[{split_name}] {label_path.name}:{line_num} "
                    f"Expected 5 values, got {len(parts)}"
                )
                continue

            try:
                class_id = int(parts[0])
                x_center = float(parts[1])
                y_center = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])
            except ValueError:
                errors.append(
                    f"[{split_name}] {label_path.name}:{line_num} "
                    f"Non-numeric values in annotation"
                )
                continue

            # Validate class ID
            if class_id < 0 or class_id >= num_classes:
                errors.append(
                    f"[{split_name}] {label_path.name}:{line_num} "
                    f"Class ID {class_id} out of range [0, {num_classes - 1}]"
                )

            # Validate coordinates (must be 0-1)
            for name, val in [("x_center", x_center), ("y_center", y_center),
                              ("width", width), ("height", height)]:
                if val < 0.0 or val > 1.0:
                    errors.append(
                        f"[{split_name}] {label_path.name}:{line_num} "
                        f"{name}={val} out of range [0, 1]"
                    )
                    break

            total_annotations += 1

    return total_annotations, errors


def main():
    parser = argparse.ArgumentParser(description="Validate YOLO dataset")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to dataset root")
    args = parser.parse_args()

    result = validate_dataset(Path(args.data_dir))
    result.print_report()

    sys.exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()
