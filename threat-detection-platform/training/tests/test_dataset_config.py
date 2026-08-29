"""
Unit tests for dataset configuration.
"""

import pytest
from pathlib import Path

from pipeline.dataset_config import DatasetConfig, create_default_weapon_config


class TestDatasetConfig:
    """Tests for DatasetConfig schema."""

    def test_valid_config(self):
        config = DatasetConfig(
            path="./datasets/test",
            train="train/images",
            val="val/images",
            nc=4,
            names={0: "handgun", 1: "rifle", 2: "knife", 3: "person"},
        )
        assert config.nc == 4
        assert config.class_names == ["handgun", "rifle", "knife", "person"]

    def test_names_count_mismatch_raises(self):
        with pytest.raises(Exception):
            DatasetConfig(
                path="./datasets/test",
                nc=4,
                names={0: "handgun", 1: "rifle"},  # Only 2, but nc=4
            )

    def test_class_names_property(self):
        config = DatasetConfig(
            path="./data",
            nc=2,
            names={0: "weapon", 1: "person"},
        )
        assert config.class_names == ["weapon", "person"]

    def test_path_properties(self):
        config = DatasetConfig(
            path="/data/weapon",
            train="train/images",
            val="val/images",
            test="test/images",
            nc=1,
            names={0: "gun"},
        )
        assert config.train_images_path == Path("/data/weapon/train/images")
        assert config.train_labels_path == Path("/data/weapon/train/labels")
        assert config.val_images_path == Path("/data/weapon/val/images")
        assert config.val_labels_path == Path("/data/weapon/val/labels")
        assert config.test_images_path == Path("/data/weapon/test/images")
        assert config.test_labels_path == Path("/data/weapon/test/labels")

    def test_no_test_split(self):
        config = DatasetConfig(
            path="./data",
            nc=1,
            names={0: "obj"},
            test=None,
        )
        assert config.test_images_path is None
        assert config.test_labels_path is None

    def test_to_yaml_and_from_yaml(self, tmp_path):
        config = DatasetConfig(
            path=str(tmp_path / "dataset"),
            nc=3,
            names={0: "a", 1: "b", 2: "c"},
        )

        yaml_path = tmp_path / "data.yaml"
        config.to_yaml(yaml_path)
        assert yaml_path.exists()

        loaded = DatasetConfig.from_yaml(yaml_path)
        assert loaded.nc == 3
        assert loaded.class_names == ["a", "b", "c"]
        assert loaded.path == str(tmp_path / "dataset")

    def test_from_yaml_not_found(self):
        with pytest.raises(FileNotFoundError):
            DatasetConfig.from_yaml(Path("/nonexistent/data.yaml"))

    def test_create_default_weapon_config(self):
        config = create_default_weapon_config("/my/dataset")
        assert config.nc == 4
        assert config.names[0] == "handgun"
        assert config.names[3] == "person"
        assert config.path == "/my/dataset"
