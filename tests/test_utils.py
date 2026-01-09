"""
Tests for the utils module.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_returns_logger(self) -> None:
        """Test that setup_logging returns a logger instance."""
        from cameraapp.utils import setup_logging

        # Clear existing handlers to avoid duplicates
        from cameraapp.config import LOGGER_NAME

        existing_logger = logging.getLogger(LOGGER_NAME)
        existing_logger.handlers.clear()

        logger = setup_logging()

        assert isinstance(logger, logging.Logger)
        assert logger.name == LOGGER_NAME

    def test_setup_logging_has_handlers(self) -> None:
        """Test that setup_logging adds handlers."""
        from cameraapp.utils import setup_logging

        from cameraapp.config import LOGGER_NAME

        existing_logger = logging.getLogger(LOGGER_NAME)
        existing_logger.handlers.clear()

        logger = setup_logging()

        assert len(logger.handlers) > 0

    def test_setup_logging_idempotent(self) -> None:
        """Test that setup_logging doesn't add duplicate handlers."""
        from cameraapp.utils import setup_logging

        from cameraapp.config import LOGGER_NAME

        existing_logger = logging.getLogger(LOGGER_NAME)
        existing_logger.handlers.clear()

        logger1 = setup_logging()
        handler_count1 = len(logger1.handlers)

        logger2 = setup_logging()
        handler_count2 = len(logger2.handlers)

        assert handler_count1 == handler_count2


class TestSaveCameras:
    """Tests for save_cameras function."""

    def test_save_cameras_creates_file(
        self,
        temp_dir: Path,
        mock_logger: logging.Logger,
    ) -> None:
        """Test that save_cameras creates a JSON file."""
        cameras_file = temp_dir / "cameras.json"

        mock_paths = MagicMock()
        mock_paths.cameras_file = cameras_file

        with patch("cameraapp.utils.PATHS", mock_paths):
            with patch("cameraapp.utils.credential_manager"):
                from cameraapp.utils import save_cameras

                # Create mock cameras
                mock_camera = MagicMock()
                mock_camera.ip = "192.168.1.100"
                mock_camera.port = 554
                mock_camera.username = "admin"
                mock_camera.password = "secret"
                mock_camera.rtsp_url = "rtsp://admin:secret@192.168.1.100/stream"
                mock_camera.camera_type = "RTSP"

                result = save_cameras([mock_camera], mock_logger)

                assert result is True
                assert cameras_file.exists()

    def test_save_cameras_json_format(
        self,
        temp_dir: Path,
        mock_logger: logging.Logger,
    ) -> None:
        """Test that save_cameras creates valid JSON."""
        cameras_file = temp_dir / "cameras.json"

        mock_paths = MagicMock()
        mock_paths.cameras_file = cameras_file

        with patch("cameraapp.utils.PATHS", mock_paths):
            with patch("cameraapp.utils.credential_manager"):
                from cameraapp.utils import save_cameras

                mock_camera = MagicMock()
                mock_camera.ip = "192.168.1.100"
                mock_camera.port = 554
                mock_camera.username = "admin"
                mock_camera.password = "secret"
                mock_camera.rtsp_url = "rtsp://test"
                mock_camera.camera_type = "RTSP"

                save_cameras([mock_camera], mock_logger)

                with open(cameras_file) as f:
                    data = json.load(f)

                assert isinstance(data, list)
                assert len(data) == 1
                assert data[0]["ip"] == "192.168.1.100"
                assert "password" not in data[0]  # Password not in JSON

    def test_save_cameras_empty_list(
        self,
        temp_dir: Path,
        mock_logger: logging.Logger,
    ) -> None:
        """Test saving empty camera list."""
        cameras_file = temp_dir / "cameras.json"

        mock_paths = MagicMock()
        mock_paths.cameras_file = cameras_file

        with patch("cameraapp.utils.PATHS", mock_paths):
            from cameraapp.utils import save_cameras

            result = save_cameras([], mock_logger)

            assert result is True
            with open(cameras_file) as f:
                data = json.load(f)
            assert data == []


class TestLoadCameras:
    """Tests for load_cameras function."""

    def test_load_cameras_missing_file(
        self,
        temp_dir: Path,
        mock_logger: logging.Logger,
    ) -> None:
        """Test loading from non-existent file returns empty list."""
        cameras_file = temp_dir / "nonexistent.json"

        mock_paths = MagicMock()
        mock_paths.cameras_file = cameras_file

        with patch("cameraapp.utils.PATHS", mock_paths):
            from cameraapp.utils import load_cameras

            result = load_cameras(mock_logger)

            assert result == []

    def test_load_cameras_valid_json(
        self,
        temp_dir: Path,
        mock_logger: logging.Logger,
        sample_camera_data: list[dict],
    ) -> None:
        """Test loading valid camera JSON."""
        cameras_file = temp_dir / "cameras.json"

        with open(cameras_file, "w") as f:
            json.dump(sample_camera_data, f)

        mock_paths = MagicMock()
        mock_paths.cameras_file = cameras_file

        with patch("cameraapp.utils.PATHS", mock_paths):
            with patch("cameraapp.utils.credential_manager") as mock_cred:
                mock_cred.retrieve_password.return_value = "test_password"

                from cameraapp.utils import load_cameras

                result = load_cameras(mock_logger)

                assert len(result) == 2
                assert result[0].ip == "192.168.1.100"
                assert result[1].ip == "192.168.1.101"

    def test_load_cameras_invalid_json(
        self,
        temp_dir: Path,
        mock_logger: logging.Logger,
    ) -> None:
        """Test loading invalid JSON returns empty list."""
        cameras_file = temp_dir / "cameras.json"

        with open(cameras_file, "w") as f:
            f.write("not valid json {{{")

        mock_paths = MagicMock()
        mock_paths.cameras_file = cameras_file

        with patch("cameraapp.utils.PATHS", mock_paths):
            from cameraapp.utils import load_cameras

            result = load_cameras(mock_logger)

            assert result == []


class TestValidateIPAddress:
    """Tests for validate_ip_address function."""

    def test_valid_ip_addresses(self) -> None:
        """Test valid IP addresses."""
        from cameraapp.utils import validate_ip_address

        assert validate_ip_address("192.168.1.1") is True
        assert validate_ip_address("10.0.0.1") is True
        assert validate_ip_address("255.255.255.255") is True
        assert validate_ip_address("0.0.0.0") is True

    def test_invalid_ip_addresses(self) -> None:
        """Test invalid IP addresses."""
        from cameraapp.utils import validate_ip_address

        assert validate_ip_address("") is False
        assert validate_ip_address("192.168.1") is False
        assert validate_ip_address("192.168.1.256") is False
        assert validate_ip_address("192.168.1.1.1") is False
        assert validate_ip_address("abc.def.ghi.jkl") is False
        assert validate_ip_address("192.168.1.-1") is False


class TestValidateRTSPUrl:
    """Tests for validate_rtsp_url function."""

    def test_valid_rtsp_urls(self) -> None:
        """Test valid RTSP URLs."""
        from cameraapp.utils import validate_rtsp_url

        assert validate_rtsp_url("rtsp://192.168.1.1/stream") is True
        assert validate_rtsp_url("RTSP://admin:pass@camera/live") is True
        assert validate_rtsp_url("rtsp://user:password@10.0.0.1:554/stream1") is True

    def test_invalid_rtsp_urls(self) -> None:
        """Test invalid RTSP URLs."""
        from cameraapp.utils import validate_rtsp_url

        assert validate_rtsp_url("") is False
        assert validate_rtsp_url("http://192.168.1.1/stream") is False
        assert validate_rtsp_url("rtp://camera/stream") is False
        assert validate_rtsp_url("192.168.1.1/stream") is False
