"""
Camera & Location specific exceptions.
"""


class CameraError(Exception):
    """Base exception for camera operations."""
    pass


class CameraNotFoundError(CameraError):
    """Raised when a camera ID does not exist."""

    def __init__(self, camera_id):
        self.camera_id = camera_id
        super().__init__(f"Camera not found: {camera_id}")


class DuplicateCameraNameError(CameraError):
    """Raised when creating a camera whose name already exists."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Camera name already in use: {name}")


class LocationError(Exception):
    """Base exception for location operations."""
    pass


class LocationNotFoundError(LocationError):
    """Raised when a location ID does not exist."""

    def __init__(self, location_id):
        self.location_id = location_id
        super().__init__(f"Location not found: {location_id}")


class DuplicateLocationNameError(LocationError):
    """Raised when creating a location whose name already exists."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Location name already in use: {name}")


class LocationInUseError(LocationError):
    """Raised when attempting to delete a location still referenced by cameras."""

    def __init__(self, location_id, camera_count: int):
        self.location_id = location_id
        self.camera_count = camera_count
        super().__init__(
            f"Location {location_id} is still referenced by {camera_count} camera(s) and cannot be deleted"
        )
