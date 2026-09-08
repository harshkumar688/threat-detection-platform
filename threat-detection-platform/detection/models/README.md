# AI Model Weights

This directory holds the YOLO detection model weights (`.pt` files) used by
the detection service. Weights are **git-ignored** (large binaries) — they
are obtained via `scripts/download_model.py`, not committed.

The detection service is **model-agnostic**: any Ultralytics-compatible YOLO
`.pt` file works without code changes, selected via the `DETECTION_MODEL_PATH`
environment variable (see `detection/src/config.py`).

## How to obtain a model

From the project root:

```bash
# Option A — base COCO model (reproducible, always works, NOT weapon-specialized)
python scripts/download_model.py --source base --model yolov8n.pt

# Option B — a weapon-specialized model from a URL you trust/reviewed
python scripts/download_model.py --source url --url https://<trusted>/weapons.pt --name weapon_detector.pt

# Option C — a model you already downloaded or trained (e.g. via Colab)
python scripts/download_model.py --source local --path /path/to/weapons.pt --name weapon_detector.pt
```

Then point the service at it:

```
DETECTION_MODEL_PATH=detection/models/weapon_detector.pt
```

## ⚠️ Model provenance — fill this in for your submission

Academic honesty requirement: record exactly which model you are using, where
it came from, and (if you measured them) its metrics on a held-out set. **Do
not claim metrics you have not measured yourself.**

| Field | Value |
|---|---|
| Model file | _e.g. weapon_detector.pt_ |
| Source (URL / repo / your Colab) | _fill in_ |
| SHA-256 (printed by download_model.py) | _fill in_ |
| Base architecture | _e.g. YOLOv8n_ |
| Classes detected | _fill in_ |
| Trained by | _you (Colab) / third party / not trained (base COCO)_ |
| Metrics (mAP/precision/recall) | _only if YOU measured them; otherwise "not measured"_ |

## Current state of this project

As of Phase 2, the pipeline has been validated live with the base COCO
`yolov8n.pt` model (which detects `knife` and `scissors`). A weapon-specialized
model can be dropped in using the options above without any code change. The
`WEAPON_CLASSES` set in `detection/src/models.py` already covers the common
firearm/blade label strings (`gun`, `pistol`, `handgun`, `rifle`, `firearm`,
`weapon`, `knife`) and is overridable via the `DETECTION_WEAPON_CLASSES`
environment variable.
