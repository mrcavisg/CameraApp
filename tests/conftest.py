"""
Pytest configuration and shared fixtures.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_logger() -> logging.Logger:
    """Create a mock logger for testing."""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def mock_paths(temp_dir: Path) -> Generator[MagicMock, None, None]:
    """Mock the PATHS configuration with temporary directory."""
    mock = MagicMock()
    mock.data_dir = temp_dir
    mock.log_dir = temp_dir / "logs"
    mock.cameras_file = temp_dir / "cameras.json"

    # Create directories
    mock.log_dir.mkdir(parents=True, exist_ok=True)

    with patch("cameraapp.config.PATHS", mock):
        yield mock


@pytest.fixture
def sample_camera_data() -> list[dict]:
    """Sample camera configuration data."""
    return [
        {
            "type": "RTSP",
            "ip": "192.168.1.100",
            "port": 554,
            "username": "admin",
            "rtsp_url": "rtsp://admin:pass@192.168.1.100:554/stream",
        },
        {
            "type": "ONVIF",
            "ip": "192.168.1.101",
            "port": 80,
            "username": "admin",
            "rtsp_url": "",
        },
    ]


@pytest.fixture
def mock_video_capture() -> Generator[MagicMock, None, None]:
    """Mock cv2.VideoCapture for testing without real cameras."""
    import numpy as np

    with patch("cv2.VideoCapture") as mock_cap:
        instance = MagicMock()
        instance.isOpened.return_value = True
        instance.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap.return_value = instance
        yield mock_cap
