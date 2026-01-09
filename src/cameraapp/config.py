"""
Configuration module for CameraApp.

Centralizes all application settings, paths, and constants.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# Try to import appdirs for cross-platform paths
try:
    from appdirs import user_data_dir
except ImportError:

    def user_data_dir(appname: str, appauthor: str) -> str:
        """Fallback function for user data directory."""
        if sys.platform.startswith("linux") or sys.platform == "darwin":
            return str(Path.home() / ".local" / "share" / appname)
        elif sys.platform == "win32":
            appdata = os.getenv("APPDATA", str(Path.home()))
            return str(Path(appdata) / appauthor / appname)
        return str(Path.home() / f".{appname.lower()}_data")


# Application Metadata
APP_NAME: Final[str] = "CameraApp"
APP_AUTHOR: Final[str] = "CFATech"
APP_VERSION: Final[str] = "1.0.0"
LOGGER_NAME: Final[str] = APP_NAME


@dataclass(frozen=True)
class Paths:
    """Application paths configuration."""

    data_dir: Path
    log_dir: Path
    cameras_file: Path

    @classmethod
    def create(cls) -> "Paths":
        """Create paths with proper error handling."""
        try:
            data_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
        except Exception:
            if getattr(sys, "frozen", False):
                base_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).parent
            data_dir = base_dir / "app_data"

        log_dir = data_dir / "logs"
        cameras_file = data_dir / "cameras.json"

        return cls(
            data_dir=data_dir,
            log_dir=log_dir,
            cameras_file=cameras_file,
        )


@dataclass(frozen=True)
class CameraSettings:
    """Camera connection settings."""

    connect_timeout_onvif: int = 10
    connect_timeout_cv_open: int = 10000
    connect_timeout_cv_read: int = 15000
    max_retries: int = 5
    retry_delay_base: int = 2
    max_retry_wait: int = 60
    frame_queue_size: int = 5
    consecutive_read_failures_limit: int = 10


@dataclass(frozen=True)
class UISettings:
    """User interface settings."""

    frame_update_interval: int = 30  # milliseconds
    default_aspect_ratio: str = "fit"
    default_window_width: int = 1280
    default_window_height: int = 720
    grid_columns: int = 2


@dataclass(frozen=True)
class LoggingSettings:
    """Logging configuration."""

    level: int = logging.DEBUG
    max_bytes: int = 5 * 1024 * 1024  # 5MB
    backup_count: int = 3
    format_string: str = (
        "%(asctime)s - %(name)s [%(levelname)s] - "
        "%(message)s (%(filename)s:%(lineno)d)"
    )


@dataclass(frozen=True)
class NetworkSettings:
    """Network configuration."""

    onvif_discovery_timeout: int = 5
    force_tcp_transport: bool = True


# Global configuration instances
PATHS = Paths.create()
CAMERA_SETTINGS = CameraSettings()
UI_SETTINGS = UISettings()
LOGGING_SETTINGS = LoggingSettings()
NETWORK_SETTINGS = NetworkSettings()

# Ensure directories exist
PATHS.data_dir.mkdir(parents=True, exist_ok=True)
PATHS.log_dir.mkdir(parents=True, exist_ok=True)
