"""
Unit tests for dataset validator.

Creates temporary dataset structures to test validation logic.
"""

import pytest
from pathlib import Path

import numpy as np
import cv2
import yaml

from pipeline.dataset_validator import validate_dataset, _validate_annotations


def create_test_dataset(base_dir: Path, num_train: int = 5, num_val: int = 2, valid: bool = True):
    """Create a minimal test dataset for validation."""
    # Create data.yaml
    config = {
        "path": str(base_dir),
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "nc": 3,
        "names": {0: "handgun", 1: "rifle", 2: "person"},
    }
    with open(base_dir / "data.yaml", "w") as f:
        yaml.dump(config, f)

    # Create directories
    for split in ["train", "val", "test"]:
        (base_dir / split / "images").mkdir(parents=True, exist_ok=True)
        (base_dir / split / "labels").mkdir(parents=True, exist_ok=True)

    # Create images and labels
    for split, count in [("train", num_train), ("val", num_val), ("test", 1)]:
        for i in range(count):
            # Image
            img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            img_path = base_dir / split / "images" / f"img_{i:04d}.jpg"
            cv2.imwrite(str(img_path), img)

            # Label
            label_path = base_dir / split / "labels" / f"img_{i:04d}.txt"
            if valid:
                label_path.write_text("0 0.5 0.5 0.3 0.4\n1 0.2 0.3 0.1 0.2\n")
            else:
                # Invalid: class_id out of range
                label_path.write_text("5 0.5 0.5 0.3 0.4\n")


class TestDatasetValidator:
    """Tests for dataset validation."""

    def test_valid_dataset(self, tmp_path):
        create_test_dataset(tmp_path, num_train=3, num_val=2, valid=True)
        result = validate_dataset(tmp_path)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_missing_data_yaml(self, tmp_path):
        result = validate_dataset(tmp_path)
        assert result.is_valid is False
        assert any("data.yaml" in e for e in result.errors)

    def test_missing_images_dir(self, tmp_path):
        # data.yaml exists but points to missing directories
        config = {"path": str(tmp_path), "train": "train/images", "val": "val/images", "nc": 1, "names": {0: "obj"}}
        with open(tmp_path / "data.yaml", "w") as f:
            yaml.dump(config, f)

        result = validate_dataset(tmp_path)
        assert result.is_valid is False
        assert any("not found" in e for e in result.errors)

    def test_invalid_annotations(self, tmp_path):
        create_test_dataset(tmp_path, num_train=2, valid=False)
        result = validate_dataset(tmp_path)
        assert result.is_valid is False
        assert any("out of range" in e for e in result.errors)

    def test_stats_computed(self, tmp_path):
        create_test_dataset(tmp_path, num_train=4, num_val=2, valid=True)
        result = validate_dataset(tmp_path)
        assert result.stats["train_images"] == 4
        assert result.stats["val_images"] == 2
        assert result.stats["total_annotations"] > 0

    def test_orphan_images_warning(self, tmp_path):
        create_test_dataset(tmp_path, num_train=3, valid=True)
        # Add an image without a label
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        cv2.imwrite(str(tmp_path / "train" / "images" / "orphan.jpg"), img)

        result = validate_dataset(tmp_path)
        # Should be valid (warnings only, not errors)
        assert result.is_valid is True
        assert any("orphan" in w or "no matching label" in w.lower() for w in result.warnings)


class TestAnnotationValidation:
    """Tests for individual annotation validation."""

    def test_valid_annotation(self, tmp_path):
        label_file = tmp_path / "good.txt"
        label_file.write_text("0 0.5 0.5 0.3 0.4\n2 0.1 0.2 0.05 0.1\n")

        count, errors = _validate_annotations(
            tmp_path, {"good": label_file}, num_classes=3, split_name="test"
        )
        assert count == 2
        assert len(errors) == 0

    def test_class_out_of_range(self, tmp_path):
        label_file = tmp_path / "bad.txt"
        label_file.write_text("5 0.5 0.5 0.3 0.4\n")

        count, errors = _validate_annotations(
            tmp_path, {"bad": label_file}, num_classes=3, split_name="test"
        )
        assert len(errors) > 0
        assert "out of range" in errors[0]

    def test_coords_out_of_range(self, tmp_path):
        label_file = tmp_path / "bad.txt"
        label_file.write_text("0 1.5 0.5 0.3 0.4\n")

        count, errors = _validate_annotations(
            tmp_path, {"bad": label_file}, num_classes=3, split_name="test"
        )
        assert len(errors) > 0
        assert "out of range" in errors[0]

    def test_wrong_column_count(self, tmp_path):
        label_file = tmp_path / "bad.txt"
        label_file.write_text("0 0.5 0.5\n")  # Only 3 values

        count, errors = _validate_annotations(
            tmp_path, {"bad": label_file}, num_classes=3, split_name="test"
        )
        assert len(errors) > 0
        assert "Expected 5" in errors[0]

    def test_empty_label_file(self, tmp_path):
        label_file = tmp_path / "empty.txt"
        label_file.write_text("")

        count, errors = _validate_annotations(
            tmp_path, {"empty": label_file}, num_classes=3, split_name="test"
        )
        assert count == 0
        assert len(errors) == 0
