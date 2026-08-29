# Dataset Directory Structure

Place your datasets here following the YOLO format.

## Required Structure

```
datasets/
└── weapon_detection/          # Dataset name
    ├── data.yaml              # Dataset config (classes, paths)
    ├── train/
    │   ├── images/            # Training images (.jpg, .png)
    │   │   ├── img_0001.jpg
    │   │   ├── img_0002.jpg
    │   │   └── ...
    │   └── labels/            # YOLO format annotations (.txt)
    │       ├── img_0001.txt
    │       ├── img_0002.txt
    │       └── ...
    ├── val/
    │   ├── images/
    │   └── labels/
    └── test/
        ├── images/
        └── labels/
```

## YOLO Annotation Format

Each `.txt` label file contains one line per object:
```
<class_id> <x_center> <y_center> <width> <height>
```

All values are normalized (0.0 - 1.0) relative to image dimensions.

Example (handgun at center of image):
```
0 0.5 0.5 0.2 0.15
```

## data.yaml Format

```yaml
path: ./datasets/weapon_detection
train: train/images
val: val/images
test: test/images

nc: 4
names:
  0: handgun
  1: rifle
  2: knife
  3: person
```

## Dataset Sources

- Custom collected and annotated images
- Open-source weapon detection datasets (with proper licensing)
- Augmented variants for robustness

**Important:** Do not commit large image datasets to git.
Add dataset directories to .gitignore and document download instructions.
