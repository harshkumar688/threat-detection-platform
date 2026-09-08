"""
Model Acquisition Script
=========================

Downloads / prepares a YOLO detection model for the platform and places it
at detection/models/<name>.pt so the detection service can load it via the
configurable model path (DETECTION_MODEL_PATH).

The platform is model-agnostic (see detection/src/inference/model_loader.py):
any Ultralytics-compatible YOLO .pt file can be dropped in without code
changes. This script simply automates obtaining one, from a DOCUMENTED and
TRUSTED source — it never pulls an unverified binary silently.

Sources supported:

  1. base     -> Downloads an official Ultralytics base model (e.g. yolov8n.pt).
                 COCO-trained. Detects "knife" and "scissors" (which this
                 platform can treat as weapons) but is NOT weapon-specialized.
                 Fully reproducible, always works, good for pipeline testing.

  2. url      -> Downloads a weapon-specialized .pt from a URL YOU provide and
                 trust (e.g. a release asset from a weapon-detection repo you
                 have reviewed, or your own Colab-trained weights). Requires
                 --url. Prints a SHA-256 of the downloaded file so the exact
                 artifact is recorded/reproducible.

  3. local    -> Copies a .pt you already downloaded/trained into the models
                 directory. Requires --path.

IMPORTANT (academic honesty):
- This script does NOT train a model. Training a weapon detector needs a
  labeled weapons dataset + GPU time (see training/ pipeline). On CPU-only
  hardware, dropping in an existing model is the practical path.
- Whatever model you use, record its provenance in detection/models/README.md.
  Do not claim metrics you have not measured yourself on a held-out set.

Usage:
    python scripts/download_model.py --source base --model yolov8n.pt
    python scripts/download_model.py --source url --url https://.../weapons.pt --name weapon_detector.pt
    python scripts/download_model.py --source local --path C:/downloads/weapons.pt --name weapon_detector.pt
"""

import argparse
import hashlib
import shutil
import sys
from pathlib import Path
from urllib.request import urlopen

# Resolve <repo>/detection/models regardless of where the script is run from.
SCRIPT_DIR = Path(__file__).resolve().parent
MODELS_DIR = SCRIPT_DIR.parent / "detection" / "models"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_base(model_name: str) -> Path:
    """
    Download an official Ultralytics base model. Ultralytics auto-downloads
    known model names on first use, so we trigger that and then copy the
    cached weights into the models directory for an explicit, versioned copy.
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ERROR: ultralytics not installed. Run: pip install ultralytics", file=sys.stderr)
        sys.exit(1)

    print(f"[base] Fetching official Ultralytics model: {model_name}")
    model = YOLO(model_name)  # triggers download to the ultralytics cache
    src = Path(model.ckpt_path) if getattr(model, "ckpt_path", None) else Path(model_name)

    dest = MODELS_DIR / model_name
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    if src.exists() and src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    elif not dest.exists() and Path(model_name).exists():
        shutil.copy2(model_name, dest)

    print(f"[base] Model available at: {dest}")
    print(f"[base] Classes: {list(model.names.values())}")
    return dest


def download_url(url: str, name: str) -> Path:
    """Download a .pt from a user-provided, trusted URL."""
    if not url.lower().startswith("https://"):
        print("ERROR: Only HTTPS URLs are allowed for security.", file=sys.stderr)
        sys.exit(1)

    dest = MODELS_DIR / name
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[url] Downloading weapon model from: {url}")
    print("[url] NOTE: you are responsible for trusting this source.")
    with urlopen(url) as resp, open(dest, "wb") as out:  # noqa: S310 (https enforced above)
        shutil.copyfileobj(resp, out)

    digest = _sha256(dest)
    print(f"[url] Saved to: {dest}")
    print(f"[url] SHA-256: {digest}")
    print("[url] Record this URL + SHA-256 in detection/models/README.md for reproducibility.")
    return dest


def copy_local(path: str, name: str) -> Path:
    """Copy a locally obtained/trained .pt into the models directory."""
    src = Path(path)
    if not src.exists():
        print(f"ERROR: File not found: {src}", file=sys.stderr)
        sys.exit(1)
    if src.suffix.lower() != ".pt":
        print(f"ERROR: Expected a .pt file, got: {src.suffix}", file=sys.stderr)
        sys.exit(1)

    dest = MODELS_DIR / name
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

    digest = _sha256(dest)
    print(f"[local] Copied to: {dest}")
    print(f"[local] SHA-256: {digest}")
    return dest


def main():
    parser = argparse.ArgumentParser(description="Acquire a YOLO model for the platform")
    parser.add_argument("--source", choices=["base", "url", "local"], default="base",
                        help="Where to get the model from (default: base)")
    parser.add_argument("--model", default="yolov8n.pt",
                        help="Base model name for --source base (default: yolov8n.pt)")
    parser.add_argument("--url", help="HTTPS URL of a .pt for --source url")
    parser.add_argument("--path", help="Local .pt path for --source local")
    parser.add_argument("--name", default="weapon_detector.pt",
                        help="Filename to save as for url/local sources (default: weapon_detector.pt)")
    args = parser.parse_args()

    if args.source == "base":
        dest = download_base(args.model)
    elif args.source == "url":
        if not args.url:
            parser.error("--source url requires --url")
        dest = download_url(args.url, args.name)
    else:  # local
        if not args.path:
            parser.error("--source local requires --path")
        dest = copy_local(args.path, args.name)

    print()
    print("Done. To use this model, set in your .env:")
    print(f"    DETECTION_MODEL_PATH={dest.as_posix()}")


if __name__ == "__main__":
    main()
