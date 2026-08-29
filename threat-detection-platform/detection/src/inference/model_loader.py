"""
Model Loader

Responsible for:
- Loading YOLO model weights from disk or Ultralytics hub
- Validating model file existence
- Selecting compute device (CPU/GPU)
- Reporting model metadata (classes, input size)

Separated from inference to allow:
- Model hot-swapping
- Model validation before use
- Unit testing without model dependency
"""

from pathlib import Path
from typing import Dict, List, Optional

from ..logger import get_logger

logger = get_logger(__name__)


class ModelLoadError(Exception):
    """Raised when model loading fails."""
    pass


class ModelLoader:
    """Loads and manages YOLO model instances."""

    def __init__(
        self,
        model_path: str,
        device: str = "auto",
        input_size: int = 640,
    ):
        """
        Initialize model loader.

        Args:
            model_path: Path to .pt weights file or Ultralytics model name (e.g., "yolov8n.pt")
            device: Compute device - "auto", "cpu", "cuda", "cuda:0"
            input_size: Model input resolution (square)
        """
        self.model_path = model_path
        self.device = device
        self.input_size = input_size
        self._model = None
        self._class_names: Dict[int, str] = {}

    def load(self):
        """
        Load the YOLO model.

        Raises:
            ModelLoadError: If model cannot be loaded.
        """
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise ModelLoadError(
                "ultralytics package not installed. Install with: pip install ultralytics"
            ) from e

        # Validate model path (if it's a file path, check existence)
        path = Path(self.model_path)
        if not self.model_path.endswith(".pt") or path.exists():
            # It's either a valid file path or a model name like "yolov8n.pt"
            pass
        elif not path.exists() and "/" in self.model_path:
            raise ModelLoadError(
                f"Model file not found: {self.model_path}. "
                f"Ensure the weights file exists at the specified path."
            )

        # Resolve device
        resolved_device = self._resolve_device()

        logger.info(
            "loading_model",
            model_path=self.model_path,
            device=resolved_device,
            input_size=self.input_size,
        )

        try:
            self._model = YOLO(self.model_path)

            # Move to device
            if resolved_device != "cpu":
                self._model.to(resolved_device)

            # Extract class names
            self._class_names = self._model.names  # Dict[int, str]

            logger.info(
                "model_loaded",
                classes=list(self._class_names.values()),
                num_classes=len(self._class_names),
                device=resolved_device,
            )

        except Exception as e:
            raise ModelLoadError(f"Failed to load model '{self.model_path}': {e}") from e

    def _resolve_device(self) -> str:
        """Resolve 'auto' device to actual device."""
        if self.device != "auto":
            return self.device

        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda:0"
                logger.info("device_selected", device=device, gpu_name=torch.cuda.get_device_name(0))
                return device
        except ImportError:
            pass

        logger.info("device_selected", device="cpu", reason="CUDA not available")
        return "cpu"

    @property
    def model(self):
        """Get the loaded model instance. Raises if not loaded."""
        if self._model is None:
            raise ModelLoadError("Model not loaded. Call load() first.")
        return self._model

    @property
    def class_names(self) -> Dict[int, str]:
        """Get model class name mapping {id: name}."""
        return self._class_names

    @property
    def class_list(self) -> List[str]:
        """Get list of class names."""
        return list(self._class_names.values())

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None

    def get_model_info(self) -> Dict:
        """Get model metadata."""
        return {
            "model_path": self.model_path,
            "device": self.device,
            "input_size": self.input_size,
            "is_loaded": self.is_loaded,
            "num_classes": len(self._class_names),
            "classes": self.class_list,
        }
