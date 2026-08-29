"""
Dataset Configuration

Defines and validates the data.yaml schema used by YOLO training.
Provides utilities to create, load, and validate dataset configs.
"""

from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, model_validator


class DatasetConfig(BaseModel):
    """Schema for data.yaml - YOLO dataset configuration."""

    path: str = Field(description="Root path to dataset directory")
    train: str = Field(default="train/images", description="Relative path to training images")
    val: str = Field(default="val/images", description="Relative path to validation images")
    test: Optional[str] = Field(default="test/images", description="Relative path to test images")
    nc: int = Field(gt=0, description="Number of classes")
    names: Dict[int, str] = Field(description="Class ID to name mapping")

    @model_validator(mode="after")
    def validate_names_count(self):
        if len(self.names) != self.nc:
            raise ValueError(
                f"Number of class names ({len(self.names)}) does not match nc ({self.nc})"
            )
        return self

    @property
    def class_names(self) -> List[str]:
        """Get ordered list of class names."""
        return [self.names[i] for i in sorted(self.names.keys())]

    @property
    def root_path(self) -> Path:
        """Get root path as Path object."""
        return Path(self.path)

    @property
    def train_images_path(self) -> Path:
        return self.root_path / self.train

    @property
    def train_labels_path(self) -> Path:
        return self.root_path / self.train.replace("images", "labels")

    @property
    def val_images_path(self) -> Path:
        return self.root_path / self.val

    @property
    def val_labels_path(self) -> Path:
        return self.root_path / self.val.replace("images", "labels")

    @property
    def test_images_path(self) -> Optional[Path]:
        if self.test:
            return self.root_path / self.test
        return None

    @property
    def test_labels_path(self) -> Optional[Path]:
        if self.test:
            return self.root_path / self.test.replace("images", "labels")
        return None

    def to_yaml(self, output_path: Path) -> None:
        """Write configuration to a YAML file."""
        data = {
            "path": self.path,
            "train": self.train,
            "val": self.val,
            "nc": self.nc,
            "names": self.names,
        }
        if self.test:
            data["test"] = self.test

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "DatasetConfig":
        """Load configuration from a YAML file."""
        if not yaml_path.exists():
            raise FileNotFoundError(f"Dataset config not found: {yaml_path}")

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        # Convert names list to dict if necessary
        if isinstance(data.get("names"), list):
            data["names"] = {i: name for i, name in enumerate(data["names"])}

        return cls(**data)


def create_default_weapon_config(dataset_dir: str) -> DatasetConfig:
    """Create default weapon detection dataset configuration."""
    return DatasetConfig(
        path=dataset_dir,
        train="train/images",
        val="val/images",
        test="test/images",
        nc=4,
        names={
            0: "handgun",
            1: "rifle",
            2: "knife",
            3: "person",
        },
    )
