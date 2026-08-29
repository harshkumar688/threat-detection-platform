"""
Detection Module - Standalone Entry Point

Run detection from the command line:
    python -m src.main --source webcam
    python -m src.main --source path/to/video.mp4
    python -m src.main --source path/to/image.jpg
    python -m src.main --source webcam --model yolov8n.pt --confidence 0.4
"""

import argparse
import sys

from .config import DetectionConfig, get_detection_config
from .inference import DetectionEngine
from .logger import setup_logging, get_logger


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AI Weapon Detection - YOLO Inference Module"
    )
    parser.add_argument(
        "--source",
        type=str,
        default="webcam",
        help="Input source: 'webcam', 'webcam:1', image path, or video path",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model path or name (default: from config/env)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=None,
        help="Confidence threshold (0.0-1.0)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device: auto, cpu, cuda, cuda:0",
    )
    parser.add_argument(
        "--input-size",
        type=int,
        default=None,
        help="Model input size (320, 640, 1280)",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Run without OpenCV display window (print results to console)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum number of frames to process (for testing)",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Build config with CLI overrides
    config = get_detection_config()
    if args.model:
        config.model_path = args.model
    if args.confidence is not None:
        config.confidence_threshold = args.confidence
    if args.device:
        config.device = args.device
    if args.input_size:
        config.input_size = args.input_size

    # Setup logging
    setup_logging(config.log_level)
    logger = get_logger("main")

    logger.info(
        "detection_module_starting",
        source=args.source,
        model=config.model_path,
        confidence=config.confidence_threshold,
        device=config.device,
    )

    # Create and start engine
    engine = DetectionEngine(config)

    try:
        engine.start()
    except Exception as e:
        logger.error("engine_start_failed", error=str(e))
        sys.exit(1)

    # Run detection
    try:
        if args.no_display:
            _run_headless(engine, args)
        else:
            engine.detect_and_display(args.source)
    except KeyboardInterrupt:
        logger.info("interrupted_by_user")
    except Exception as e:
        logger.error("detection_error", error=str(e))
        sys.exit(1)
    finally:
        engine.stop()
        logger.info("detection_module_stopped")


def _run_headless(engine: DetectionEngine, args: argparse.Namespace):
    """Run detection without display, printing results to console."""
    logger = get_logger("headless")
    frame_count = 0

    if args.source.startswith("webcam"):
        gen = engine.detect_webcam(annotate=False)
    else:
        gen = engine.detect_video(args.source, annotate=False)

    for result, _ in gen:
        frame_count += 1

        if result.detections:
            print(
                f"[Frame {result.frame_number}] "
                f"{result.detection_count} detections "
                f"({result.inference_time_ms:.1f}ms)"
            )
            for det in result.detections:
                marker = "⚠️ WEAPON" if det.is_weapon else "  "
                print(
                    f"  {marker} {det.class_name}: "
                    f"{det.confidence:.3f} "
                    f"@ ({det.bbox.x1:.2f},{det.bbox.y1:.2f})-({det.bbox.x2:.2f},{det.bbox.y2:.2f})"
                )

        if args.max_frames and frame_count >= args.max_frames:
            logger.info("max_frames_reached", count=frame_count)
            break

    logger.info("processing_complete", total_frames=frame_count)


if __name__ == "__main__":
    main()
