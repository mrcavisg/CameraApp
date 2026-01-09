"""
Utility module for CameraApp.

Provides logging setup, camera persistence, and helper functions.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from cameraapp.config import (
    LOGGER_NAME,
    LOGGING_SETTINGS,
    PATHS,
)

if TYPE_CHECKING:
    from cameraapp.camera import Camera

logger = logging.getLogger(LOGGER_NAME)


def setup_logging() -> logging.Logger:
    """
    Configure and return the application logger.

    Sets up both console and rotating file handlers with
    the configured format and log levels.

    Returns:
        Configured logger instance
    """
    app_logger = logging.getLogger(LOGGER_NAME)

    # Avoid duplicate handlers
    if app_logger.handlers:
        return app_logger

    app_logger.setLevel(LOGGING_SETTINGS.level)

    # Create log directory
    log_file_path = PATHS.log_dir / "cameraapp.log"
    try:
        PATHS.log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create log directory: {e}", file=sys.stderr)
        log_file_path = Path(__file__).parent / "cameraapp.log"

    formatter = logging.Formatter(LOGGING_SETTINGS.format_string)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOGGING_SETTINGS.level)
    console_handler.setFormatter(formatter)
    app_logger.addHandler(console_handler)

    # Rotating file handler
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=LOGGING_SETTINGS.max_bytes,
            backupCount=LOGGING_SETTINGS.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(LOGGING_SETTINGS.level)
        file_handler.setFormatter(formatter)
        app_logger.addHandler(file_handler)
        app_logger.info(f"Logging initialized. File: {log_file_path}")
    except PermissionError as e:
        app_logger.error(f"No permission to write log file: {log_file_path} - {e}")
    except Exception as e:
        app_logger.error(f"Failed to setup file logging: {e}", exc_info=True)

    return app_logger


def save_cameras(cameras: list[Camera], log: Optional[logging.Logger] = None) -> bool:
    """
    Save camera configurations to JSON file.

    Passwords are stored securely using the credential manager,
    not in the JSON file.

    Args:
        cameras: List of Camera objects to save
        log: Optional logger instance

    Returns:
        True if save was successful
    """
    from cameraapp.security import credential_manager

    log = log or logger

    try:
        camera_data: list[dict[str, Any]] = []

        for cam in cameras:
            if not _is_valid_camera(cam):
                log.warning(f"Skipping invalid camera object: {type(cam)}")
                continue

            # Store password securely
            if cam.password:
                credential_manager.store_password(cam.ip, cam.port, cam.password)

            # Save camera data without password
            camera_data.append({
                "type": getattr(cam, "camera_type", "RTSP"),
                "ip": cam.ip,
                "port": cam.port,
                "username": cam.username,
                "rtsp_url": cam.rtsp_url,
                # Password is NOT stored here - it's in secure storage
            })

        # Create directory and save
        PATHS.cameras_file.parent.mkdir(parents=True, exist_ok=True)
        with open(PATHS.cameras_file, "w", encoding="utf-8") as f:
            json.dump(camera_data, f, indent=4)

        log.info(f"Saved {len(camera_data)} cameras to {PATHS.cameras_file}")
        return True

    except PermissionError as e:
        log.error(f"No permission to write config file: {PATHS.cameras_file} - {e}")
        return False
    except Exception as e:
        log.error(f"Error saving cameras: {e}", exc_info=True)
        return False


def load_cameras(log: Optional[logging.Logger] = None) -> list[Camera]:
    """
    Load camera configurations from JSON file.

    Passwords are retrieved from secure storage.

    Args:
        log: Optional logger instance

    Returns:
        List of Camera objects
    """
    from cameraapp.camera import Camera
    from cameraapp.security import credential_manager

    log = log or logger
    cameras: list[Camera] = []

    if not PATHS.cameras_file.exists():
        log.warning(f"Config file not found: {PATHS.cameras_file}")
        return cameras

    try:
        with open(PATHS.cameras_file, "r", encoding="utf-8") as f:
            camera_data = json.load(f)

        log.debug(f"Loaded data from JSON: {len(camera_data)} entries")

        for data in camera_data:
            required_keys = ["ip", "port", "username"]
            if not all(k in data for k in required_keys):
                missing = [k for k in required_keys if k not in data]
                log.warning(f"Incomplete camera data (missing: {missing}): {data}")
                continue

            try:
                ip = data["ip"]
                port = int(data["port"])

                # Retrieve password from secure storage
                password = credential_manager.retrieve_password(ip, port) or ""

                cam = Camera(
                    ip=ip,
                    port=port,
                    username=data["username"],
                    password=password,
                    rtsp_url=data.get("rtsp_url", ""),
                    camera_type=data.get("type", "RTSP"),
                )
                cameras.append(cam)

            except ValueError as e:
                log.error(f"Error converting data for IP {data.get('ip', '?')}: {e}")
            except TypeError as e:
                log.error(
                    f"Type error creating Camera for IP {data.get('ip', '?')}: {e}",
                    exc_info=True,
                )
            except Exception as e:
                log.error(
                    f"Unexpected error creating Camera for IP {data.get('ip', '?')}: {e}",
                    exc_info=True,
                )

        log.info(f"Loaded {len(cameras)} cameras from {PATHS.cameras_file}")

    except json.JSONDecodeError as e:
        log.error(f"Error decoding JSON {PATHS.cameras_file}: {e}")
    except Exception as e:
        log.error(f"Unexpected error loading cameras: {e}", exc_info=True)

    return cameras


def _is_valid_camera(cam: Any) -> bool:
    """Check if an object has required camera attributes."""
    required_attrs = ["ip", "port", "username", "password", "rtsp_url", "camera_type"]
    return all(hasattr(cam, attr) for attr in required_attrs)


def center_window(window: tk.Misc) -> None:
    """
    Center a tkinter window on the screen.

    Args:
        window: The tkinter window to center
    """
    try:
        if not window.winfo_exists():
            return

        window.update_idletasks()

        width = window.winfo_width()
        height = window.winfo_height()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        x = max(0, (screen_width // 2) - (width // 2))
        y = max(0, (screen_height // 2) - (height // 2))

        window.geometry(f"{width}x{height}+{x}+{y}")

        # Bring window to front temporarily
        window.lift()
        window.attributes("-topmost", True)
        window.after(100, lambda: window.attributes("-topmost", False))

        if window.winfo_exists() and window.state() == "iconic":
            window.deiconify()

        window.focus_force()

    except tk.TclError as e:
        if "application has been destroyed" not in str(e):
            logger.error(f"Tcl error centering window: {e}")
    except Exception as e:
        logger.error(f"Error centering window: {e}", exc_info=True)


def validate_ip_address(ip: str) -> bool:
    """
    Validate an IP address format.

    Args:
        ip: IP address string to validate

    Returns:
        True if valid IPv4 address
    """
    parts = ip.split(".")
    if len(parts) != 4:
        return False

    for part in parts:
        try:
            num = int(part)
            if num < 0 or num > 255:
                return False
        except ValueError:
            return False

    return True


def validate_rtsp_url(url: str) -> bool:
    """
    Validate an RTSP URL format.

    Args:
        url: URL string to validate

    Returns:
        True if valid RTSP URL
    """
    return url.lower().startswith("rtsp://")
