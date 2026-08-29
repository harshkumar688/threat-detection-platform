"""
Training Script

Executes a YOLO training run from a YAML configuration file.
Manages experiment naming, checkpoint saving, and logging.

Usage:
    python -m pipeline.train --config configs/train_yolov8m.yaml
    python -m pipeline.train --config configs/train_yolov8n_quick.yaml --device cpu
"""

import argparse
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import yaml


def load_config(config_path: str) -> Dict:
    """Load and validate training configuration."""
    path = Path(config_path)
    if not path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    with open(path) as f:
        config = yaml.safe_load(f)

    # Validate required sections
    required_sections = ["experiment", "dataset", "model", "training"]
    for section in required_sections:
        if section not in config:
            print(f"ERROR: Missing required section '{section}' in config")
            sys.exit(1)

    return config


def train(config: Dict, device_override: Optional[str] = None) -> Path:
    """
    Execute training run.

    Args:
        config: Parsed YAML configuration dict.
        device_override: Override device setting from CLI.

    Returns:
        Path to the output directory containing results and weights.
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ERROR: ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    # Extract config sections
    experiment = config["experiment"]
    dataset = config["dataset"]
    model_cfg = config["model"]
    training = config["training"]
    hardware = config.get("hardware", {})
    output = config.get("output", {})

    # Resolve paths
    data_yaml = dataset["data_yaml"]
    if not Path(data_yaml).exists():
        print(f"ERROR: Dataset config not found: {data_yaml}")
        sys.exit(1)

    # Device
    device = device_override or hardware.get("device", "auto")
    if device == "auto":
        import torch
        device = "0" if torch.cuda.is_available() else "cpu"

    # Experiment name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_name = f"{experiment['name']}_{timestamp}"

    print("\n" + "=" * 70)
    print("TRAINING CONFIGURATION")
    print("=" * 70)
    print(f"  Experiment:  {exp_name}")
    print(f"  Description: {experiment.get('description', 'N/A')}")
    print(f"  Base model:  {model_cfg['base']}")
    print(f"  Dataset:     {data_yaml}")
    print(f"  Epochs:      {training['epochs']}")
    print(f"  Batch size:  {training['batch_size']}")
    print(f"  Image size:  {training['imgsz']}")
    print(f"  Device:      {device}")
    print(f"  AMP:         {hardware.get('amp', True)}")
    print("=" * 70 + "\n")

    # Load model
    model = YOLO(model_cfg["base"])

    # Build training arguments
    train_args = {
        "data": data_yaml,
        "epochs": training["epochs"],
        "batch": training["batch_size"],
        "imgsz": training["imgsz"],
        "device": device,
        "workers": hardware.get("workers", 8),
        "amp": hardware.get("amp", True),
        "project": output.get("project", "runs"),
        "name": exp_name,
        "exist_ok": output.get("exist_ok", False),
        "patience": training.get("patience", 20),
        "save_period": output.get("save_period", -1),
        "plots": output.get("plots", True),
        "optimizer": training.get("optimizer", "auto"),
        "lr0": training.get("lr0", 0.01),
        "lrf": training.get("lrf", 0.01),
        "momentum": training.get("momentum", 0.937),
        "weight_decay": training.get("weight_decay", 0.0005),
        "warmup_epochs": training.get("warmup_epochs", 3.0),
        "warmup_momentum": training.get("warmup_momentum", 0.8),
        "warmup_bias_lr": training.get("warmup_bias_lr", 0.1),
        "box": training.get("box", 7.5),
        "cls": training.get("cls", 0.5),
        "dfl": training.get("dfl", 1.5),
    }

    # Augmentation parameters
    aug = training.get("augmentation", {})
    for key in ["hsv_h", "hsv_s", "hsv_v", "degrees", "translate", "scale",
                "shear", "perspective", "flipud", "fliplr", "mosaic", "mixup", "copy_paste"]:
        if key in aug:
            train_args[key] = aug[key]

    # Save config copy to output
    output_dir = Path(train_args["project"]) / exp_name
    output_dir.mkdir(parents=True, exist_ok=True)
    config_copy_path = output_dir / "train_config.yaml"
    with open(config_copy_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    # Start training
    start_time = time.time()
    results = model.train(**train_args)
    duration = time.time() - start_time

    # Report
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)
    print(f"  Duration:    {duration / 60:.1f} minutes")
    print(f"  Output:      {output_dir}")
    print(f"  Best model:  {output_dir / 'weights' / 'best.pt'}")
    print(f"  Last model:  {output_dir / 'weights' / 'last.pt'}")
    print("=" * 70 + "\n")

    return output_dir


def main():
    parser = argparse.ArgumentParser(description="Train YOLO weapon detector")
    parser.add_argument("--config", type=str, required=True, help="Path to training config YAML")
    parser.add_argument("--device", type=str, default=None, help="Override device (cpu, 0, 0,1)")
    args = parser.parse_args()

    config = load_config(args.config)
    train(config, device_override=args.device)


if __name__ == "__main__":
    main()
