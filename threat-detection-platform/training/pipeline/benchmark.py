"""
Inference Speed Benchmark

Measures actual inference speed (FPS) of a trained model on the target hardware.
Reports:
- Average inference time per frame
- FPS (frames per second)
- Preprocessing time
- Postprocessing time
- Total pipeline time

Usage:
    python -m pipeline.benchmark --model runs/experiment/weights/best.pt
    python -m pipeline.benchmark --model runs/experiment/weights/best.pt --imgsz 640 --device cpu --warmup 20 --iterations 100
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Dict

import numpy as np


def benchmark_model(
    model_path: str,
    imgsz: int = 640,
    device: str = "auto",
    warmup: int = 10,
    iterations: int = 100,
    batch_size: int = 1,
) -> Dict:
    """
    Benchmark model inference speed.

    Args:
        model_path: Path to .pt model weights.
        imgsz: Input image size.
        device: Compute device.
        warmup: Number of warmup iterations (not timed).
        iterations: Number of timed iterations.
        batch_size: Batch size for inference.

    Returns:
        Dictionary with timing measurements.
    """
    try:
        from ultralytics import YOLO
        import torch
    except ImportError:
        print("ERROR: ultralytics/torch not installed")
        sys.exit(1)

    if not Path(model_path).exists():
        print(f"ERROR: Model not found: {model_path}")
        sys.exit(1)

    # Resolve device
    if device == "auto":
        device = "0" if torch.cuda.is_available() else "cpu"

    actual_device = f"cuda:{device}" if device.isdigit() else device
    device_name = "CPU"
    if device.isdigit() and torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(int(device))

    print(f"\n{'=' * 60}")
    print(f"INFERENCE SPEED BENCHMARK")
    print(f"{'=' * 60}")
    print(f"  Model:      {model_path}")
    print(f"  Image size: {imgsz}x{imgsz}")
    print(f"  Device:     {actual_device} ({device_name})")
    print(f"  Batch size: {batch_size}")
    print(f"  Warmup:     {warmup} iterations")
    print(f"  Timed:      {iterations} iterations")
    print()

    # Load model
    model = YOLO(model_path)

    # Create synthetic input
    dummy_input = np.random.randint(0, 255, (imgsz, imgsz, 3), dtype=np.uint8)

    # Warmup
    print("Running warmup...")
    for _ in range(warmup):
        model.predict(source=dummy_input, imgsz=imgsz, device=device, verbose=False)

    # Synchronize GPU before timing
    if device.isdigit() and torch.cuda.is_available():
        torch.cuda.synchronize()

    # Timed iterations
    print(f"Running {iterations} timed iterations...")
    times_ms = []

    for i in range(iterations):
        if device.isdigit() and torch.cuda.is_available():
            torch.cuda.synchronize()

        start = time.perf_counter()
        model.predict(source=dummy_input, imgsz=imgsz, device=device, verbose=False)

        if device.isdigit() and torch.cuda.is_available():
            torch.cuda.synchronize()

        elapsed_ms = (time.perf_counter() - start) * 1000
        times_ms.append(elapsed_ms)

    # Compute statistics
    times_array = np.array(times_ms)
    results = {
        "model": model_path,
        "device": actual_device,
        "device_name": device_name,
        "imgsz": imgsz,
        "batch_size": batch_size,
        "iterations": iterations,
        "timing_ms": {
            "mean": float(np.mean(times_array)),
            "median": float(np.median(times_array)),
            "std": float(np.std(times_array)),
            "min": float(np.min(times_array)),
            "max": float(np.max(times_array)),
            "p95": float(np.percentile(times_array, 95)),
            "p99": float(np.percentile(times_array, 99)),
        },
        "fps": {
            "mean": float(1000.0 / np.mean(times_array)),
            "median": float(1000.0 / np.median(times_array)),
            "min": float(1000.0 / np.max(times_array)),  # Min FPS = Max time
            "max": float(1000.0 / np.min(times_array)),  # Max FPS = Min time
        },
    }

    # Print results
    print(f"\n{'=' * 60}")
    print(f"BENCHMARK RESULTS")
    print(f"{'=' * 60}")
    print(f"\n  --- Inference Time (ms/frame) ---")
    print(f"  Mean:     {results['timing_ms']['mean']:.2f} ms")
    print(f"  Median:   {results['timing_ms']['median']:.2f} ms")
    print(f"  Std Dev:  {results['timing_ms']['std']:.2f} ms")
    print(f"  Min:      {results['timing_ms']['min']:.2f} ms")
    print(f"  Max:      {results['timing_ms']['max']:.2f} ms")
    print(f"  P95:      {results['timing_ms']['p95']:.2f} ms")
    print(f"  P99:      {results['timing_ms']['p99']:.2f} ms")
    print(f"\n  --- Throughput (FPS) ---")
    print(f"  Mean:     {results['fps']['mean']:.1f} FPS")
    print(f"  Median:   {results['fps']['median']:.1f} FPS")
    print(f"  Min:      {results['fps']['min']:.1f} FPS")
    print(f"  Max:      {results['fps']['max']:.1f} FPS")

    # Assess against requirements
    print(f"\n  --- Requirement Check ---")
    nfr_gpu = 15.0  # NFR-001: ≥15 FPS on GPU
    nfr_cpu = 5.0   # NFR-002: ≥5 FPS on CPU
    target = nfr_gpu if "cuda" in actual_device else nfr_cpu
    mean_fps = results["fps"]["mean"]
    status = "✅ PASS" if mean_fps >= target else "❌ FAIL"
    print(f"  Target: ≥{target:.0f} FPS | Achieved: {mean_fps:.1f} FPS | {status}")

    print(f"\n{'=' * 60}\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark model inference speed")
    parser.add_argument("--model", type=str, required=True, help="Path to .pt model")
    parser.add_argument("--imgsz", type=int, default=640, help="Input size")
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--warmup", type=int, default=10, help="Warmup iterations")
    parser.add_argument("--iterations", type=int, default=100, help="Timed iterations")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size")
    args = parser.parse_args()

    benchmark_model(
        model_path=args.model,
        imgsz=args.imgsz,
        device=args.device,
        warmup=args.warmup,
        iterations=args.iterations,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
