# Training Pipeline

Reproducible object-detection training pipeline for the Threat Detection Platform.

## Quick Start

```bash
# 1. Prepare dataset
python -m pipeline.dataset_validator --data-dir datasets/weapon_detection

# 2. View dataset statistics
python -m pipeline.dataset_stats --data-dir datasets/weapon_detection

# 3. Train
python -m pipeline.train --config configs/train_yolov8m.yaml

# 4. Evaluate
python -m pipeline.evaluate --model runs/experiment_name/weights/best.pt --data-dir datasets/weapon_detection

# 5. Measure speed
python -m pipeline.benchmark --model runs/experiment_name/weights/best.pt
```

See each module's docstring for detailed usage.
