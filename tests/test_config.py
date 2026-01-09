"""
Tests for the config module.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest


class TestPaths:
    """Tests for Paths configuration."""

    def test_paths_create(self) -> None:
        """Test that Paths.create() returns valid paths."""
        from cameraapp.config import Paths

        paths = Paths.create()

        assert isinstance(paths.data_dir, Path)
        assert isinstance(paths.log_dir, Path)
        assert isinstance(paths.cameras_file, Path)

    def test_paths_are_absolute(self) -> None:
        """Test that all paths are absolute."""
        from cameraapp.config import Paths

        paths = Paths.create()

        assert paths.data_dir.is_absolute()
        assert paths.log_dir.is_absolute()
        assert paths.cameras_file.is_absolute()

    def test_log_dir_is_under_data_dir(self) -> None:
        """Test that log directory is under data directory."""
        from cameraapp.config import Paths

        paths = Paths.create()

        assert str(paths.log_dir).startswith(str(paths.data_dir))

    def test_cameras_file_is_under_data_dir(self) -> None:
        """Test that cameras file is under data directory."""
        from cameraapp.config import Paths

        paths = Paths.create()

        assert str(paths.cameras_file).startswith(str(paths.data_dir))


class TestCameraSettings:
    """Tests for CameraSettings configuration."""

    def test_camera_settings_defaults(self) -> None:
        """Test default camera settings values."""
        from cameraapp.config import CameraSettings

        settings = CameraSettings()

        assert settings.connect_timeout_onvif == 10
        assert settings.connect_timeout_cv_open == 10000
        assert settings.connect_timeout_cv_read == 15000
        assert settings.max_retries == 5
        assert settings.retry_delay_base == 2
        assert settings.max_retry_wait == 60
        assert settings.frame_queue_size == 5
        assert settings.consecutive_read_failures_limit == 10

    def test_camera_settings_immutable(self) -> None:
        """Test that CameraSettings is immutable (frozen dataclass)."""
        from cameraapp.config import CameraSettings

        settings = CameraSettings()

        with pytest.raises(Exception):  # FrozenInstanceError
            settings.max_retries = 10  # type: ignore


class TestUISettings:
    """Tests for UISettings configuration."""

    def test_ui_settings_defaults(self) -> None:
        """Test default UI settings values."""
        from cameraapp.config import UISettings

        settings = UISettings()

        assert settings.frame_update_interval == 30
        assert settings.default_aspect_ratio == "fit"
        assert settings.default_window_width == 1280
        assert settings.default_window_height == 720
        assert settings.grid_columns == 2


class TestLoggingSettings:
    """Tests for LoggingSettings configuration."""

    def test_logging_settings_defaults(self) -> None:
        """Test default logging settings values."""
        from cameraapp.config import LoggingSettings

        settings = LoggingSettings()

        assert settings.level == logging.DEBUG
        assert settings.max_bytes == 5 * 1024 * 1024
        assert settings.backup_count == 3
        assert "%(asctime)s" in settings.format_string


class TestGlobalConfig:
    """Tests for global configuration instances."""

    def test_global_paths_exists(self) -> None:
        """Test that global PATHS is available."""
        from cameraapp.config import PATHS

        assert PATHS is not None
        assert hasattr(PATHS, "data_dir")

    def test_global_camera_settings_exists(self) -> None:
        """Test that global CAMERA_SETTINGS is available."""
        from cameraapp.config import CAMERA_SETTINGS

        assert CAMERA_SETTINGS is not None
        assert hasattr(CAMERA_SETTINGS, "max_retries")

    def test_app_constants(self) -> None:
        """Test application constants."""
        from cameraapp.config import APP_AUTHOR, APP_NAME, APP_VERSION, LOGGER_NAME

        assert APP_NAME == "CameraApp"
        assert APP_AUTHOR == "CFATech"
        assert APP_VERSION == "1.0.0"
        assert LOGGER_NAME == APP_NAME
