"""
Unit tests for FrameSource.

Tests file validation and source type detection (without actual video I/O).
"""

import pytest
import numpy as np
from pathlib import Path

from src.inference.frame_source import (
    FrameSource,
    FrameSourceError,
    is_image_file,
    is_video_file,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)


class TestFileTypeDetection:
    """Tests for file type detection helpers."""

    def test_image_extensions(self):
        assert is_image_file("photo.jpg") is True
        assert is_image_file("photo.jpeg") is True
        assert is_image_file("photo.png") is True
        assert is_image_file("photo.bmp") is True
        assert is_image_file("photo.webp") is True

    def test_video_extensions(self):
        assert is_video_file("clip.mp4") is True
        assert is_video_file("clip.avi") is True
        assert is_video_file("clip.mkv") is True
        assert is_video_file("clip.mov") is True
        assert is_video_file("clip.wmv") is True

    def test_not_image(self):
        assert is_image_file("file.txt") is False
        assert is_image_file("video.mp4") is False
        assert is_image_file("model.pt") is False

    def test_not_video(self):
        assert is_video_file("photo.jpg") is False
        assert is_video_file("data.csv") is False
        assert is_video_file("model.pt") is False

    def test_case_insensitive(self):
        assert is_image_file("PHOTO.JPG") is True
        assert is_image_file("Photo.PNG") is True
        assert is_video_file("VIDEO.MP4") is True

    def test_path_with_directories(self):
        assert is_image_file("/path/to/image.jpg") is True
        assert is_video_file("C:/videos/clip.mp4") is True


class TestFrameSourceErrors:
    """Tests for FrameSource error handling."""

    def test_image_not_found(self):
        with pytest.raises(FrameSourceError, match="not found"):
            FrameSource.from_image("/nonexistent/path/image.jpg")

    def test_video_not_found(self):
        with pytest.raises(FrameSourceError, match="not found"):
            FrameSource.from_video("/nonexistent/path/video.mp4")

    def test_unsupported_image_format(self, tmp_path):
        # Create a file with unsupported extension
        fake_file = tmp_path / "data.txt"
        fake_file.write_text("not an image")
        with pytest.raises(FrameSourceError, match="Unsupported image format"):
            FrameSource.from_image(str(fake_file))

    def test_unsupported_video_format(self, tmp_path):
        fake_file = tmp_path / "data.txt"
        fake_file.write_text("not a video")
        with pytest.raises(FrameSourceError, match="Unsupported video format"):
            FrameSource.from_video(str(fake_file))

    def test_corrupt_image(self, tmp_path):
        # Create a file with image extension but invalid content
        fake_img = tmp_path / "corrupt.jpg"
        fake_img.write_bytes(b"not jpeg data")
        with pytest.raises(FrameSourceError, match="Failed to read"):
            FrameSource.from_image(str(fake_img))


class TestFrameSourceImage:
    """Tests for image frame source (with real test image)."""

    def test_valid_image(self, tmp_path):
        # Create a valid test image
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        img_path = tmp_path / "test.png"

        import cv2
        cv2.imwrite(str(img_path), img)

        source = FrameSource.from_image(str(img_path))
        assert source.source_type == "image"
        assert source.total_frames == 1
        assert source.resolution == (200, 100)

    def test_image_yields_one_frame(self, tmp_path):
        img = np.ones((50, 80, 3), dtype=np.uint8) * 128
        img_path = tmp_path / "test.png"

        import cv2
        cv2.imwrite(str(img_path), img)

        source = FrameSource.from_image(str(img_path))
        frames = list(source.frames())
        assert len(frames) == 1

        frame, frame_num = frames[0]
        assert frame.shape == (50, 80, 3)
        assert frame_num == 1
