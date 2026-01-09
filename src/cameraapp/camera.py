"""
Camera module for CameraApp.

Handles camera connections, frame capture, and ONVIF discovery.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from enum import Enum, auto
from typing import Optional

import cv2
import numpy as np
from numpy.typing import NDArray

from cameraapp.config import CAMERA_SETTINGS, LOGGER_NAME

# Try to import ONVIFCamera
try:
    from onvif import ONVIFCamera

    ONVIF_AVAILABLE = True
except ImportError:
    ONVIFCamera = None
    ONVIF_AVAILABLE = False


logger = logging.getLogger(LOGGER_NAME)


class CameraType(Enum):
    """Camera connection type enumeration."""

    RTSP = auto()
    ONVIF = auto()


class CameraState(Enum):
    """Camera connection state enumeration."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


class Camera:
    """
    Represents an IP camera with RTSP/ONVIF support.

    Handles connection management, frame capture in a background thread,
    and automatic reconnection on failures.

    Attributes:
        ip: Camera IP address
        port: Camera port number
        username: Authentication username
        password: Authentication password
        rtsp_url: Direct RTSP URL (optional)
        camera_type: Type of camera connection (RTSP or ONVIF)
        connected: Whether the camera is currently connected
    """

    def __init__(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        rtsp_url: str = "",
        camera_type: str = "RTSP",
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize a Camera instance.

        Args:
            ip: Camera IP address
            port: Camera port number
            username: Authentication username
            password: Authentication password
            rtsp_url: Direct RTSP URL (optional)
            camera_type: Type of camera ("RTSP" or "ONVIF")
            logger_instance: Optional logger instance
        """
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.rtsp_url = rtsp_url
        self._logger = logger_instance or logger

        # Determine camera type
        self.camera_type = self._determine_camera_type(camera_type, rtsp_url)

        self._logger.info(
            f"Camera created: IP={ip}, Port={port}, "
            f"User={username}, Type={self.camera_type}"
        )

        # Connection state
        self._onvif_cam: Optional[ONVIFCamera] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._connected = False
        self._state = CameraState.DISCONNECTED

        # Threading components
        self._frame_queue: queue.Queue[NDArray[np.uint8]] = queue.Queue(
            maxsize=CAMERA_SETTINGS.frame_queue_size
        )
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _determine_camera_type(self, camera_type: str, rtsp_url: str) -> str:
        """Determine the actual camera type based on inputs."""
        if rtsp_url and camera_type.upper() == "ONVIF":
            self._logger.warning(
                f"RTSP URL provided for {self.ip}, treating as RTSP type"
            )
            return "RTSP"
        if not rtsp_url and camera_type.upper() == "RTSP":
            self._logger.warning(
                f"Empty RTSP URL for {self.ip}, assuming ONVIF type"
            )
            return "ONVIF"
        return camera_type.upper()

    @property
    def connected(self) -> bool:
        """Return whether the camera is connected."""
        return self._connected

    @connected.setter
    def connected(self, value: bool) -> None:
        """Set the connected state."""
        self._connected = value
        self._state = CameraState.CONNECTED if value else CameraState.DISCONNECTED

    @property
    def state(self) -> CameraState:
        """Return the current camera state."""
        return self._state

    def get_rtsp_url_from_onvif(self, timeout: int = 10) -> Optional[str]:
        """
        Discover RTSP URL using ONVIF protocol.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            Discovered RTSP URL or None if discovery failed
        """
        if not ONVIF_AVAILABLE:
            self._logger.error("ONVIF library not available")
            return None

        self._logger.info(f"Discovering RTSP URL via ONVIF for {self.ip}:{self.port}")

        try:
            self._onvif_cam = ONVIFCamera(
                self.ip,
                self.port,
                self.username,
                self.password,
                no_cache=True,
                adjust_time=True,
                connect_timeout=timeout,
            )

            media = self._onvif_cam.create_media_service()
            profiles = media.GetProfiles()

            if not profiles:
                self._logger.error(f"No ONVIF profiles found for {self.ip}")
                return None

            profile = profiles[0]
            stream_uri_params = {
                "StreamSetup": {
                    "Stream": "RTP-Unicast",
                    "Transport": {"Protocol": "RTSP"},
                },
                "ProfileToken": profile.token,
            }

            stream_uri = media.GetStreamUri(stream_uri_params)
            discovered_url = stream_uri.Uri

            self._logger.info(f"Discovered RTSP URL via ONVIF: {discovered_url}")
            return discovered_url

        except Exception as e:
            self._logger.error(
                f"ONVIF discovery error for {self.ip}: {e}", exc_info=True
            )
            return None

    def connect(
        self,
        timeout_open: int = CAMERA_SETTINGS.connect_timeout_cv_open,
        timeout_read: int = CAMERA_SETTINGS.connect_timeout_cv_read,
    ) -> bool:
        """
        Connect to the camera and start frame capture thread.

        Args:
            timeout_open: OpenCV open timeout in milliseconds
            timeout_read: OpenCV read timeout in milliseconds

        Returns:
            True if connection was successful
        """
        self._logger.debug(f"Connecting to {self.ip} (Type: {self.camera_type})...")
        self._state = CameraState.CONNECTING
        self._stop_event.clear()

        # Get RTSP URL
        rtsp_url = self.rtsp_url
        if self.camera_type == "ONVIF" and not rtsp_url:
            rtsp_url = self.get_rtsp_url_from_onvif()
            if not rtsp_url:
                self._logger.error(f"Failed to get RTSP URL for {self.ip}")
                self._state = CameraState.ERROR
                return False

        if not rtsp_url:
            self._logger.error(f"No RTSP URL available for {self.ip}")
            self._state = CameraState.ERROR
            return False

        # Add TCP transport if not present
        url_to_connect = rtsp_url
        if ";transport=tcp" not in rtsp_url.lower():
            url_to_connect += ";transport=tcp"

        self._logger.info(f"Connecting with cv2.VideoCapture: {self._mask_url(url_to_connect)}")

        try:
            # Release previous capture
            with self._lock:
                if self._cap:
                    self._cap.release()
                    self._cap = None

                self._cap = cv2.VideoCapture(url_to_connect, cv2.CAP_FFMPEG)
                self._cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_open)
                self._cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_read)
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)

                if not self._cap.isOpened():
                    self._logger.error(
                        f"Failed to open RTSP stream: {self._mask_url(url_to_connect)}"
                    )
                    self._cap.release()
                    self._cap = None
                    self._state = CameraState.ERROR
                    return False

            self._logger.info(f"VideoCapture opened successfully for {self.ip}")
            self._connected = True
            self._state = CameraState.CONNECTED
            self.rtsp_url = rtsp_url

            # Start reader thread
            self._start_reader_thread()
            return True

        except Exception as e:
            self._logger.error(f"Exception connecting to {self.ip}: {e}", exc_info=True)
            with self._lock:
                if self._cap:
                    self._cap.release()
                    self._cap = None
            self._connected = False
            self._state = CameraState.ERROR
            return False

    def _mask_url(self, url: str) -> str:
        """Mask password in URL for logging."""
        if "@" in url and ":" in url:
            # Basic password masking
            parts = url.split("@")
            if len(parts) == 2:
                prefix = parts[0]
                if ":" in prefix:
                    scheme_user = prefix.rsplit(":", 1)[0]
                    return f"{scheme_user}:****@{parts[1]}"
        return url

    def _start_reader_thread(self) -> None:
        """Start the frame reader thread."""
        # Stop existing thread
        if self._thread and self._thread.is_alive():
            self._logger.warning(f"Stopping existing thread for {self.ip}")
            self._stop_event.set()
            self._thread.join(timeout=1)

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._read_frames,
            name=f"CamReader_{self.ip}",
            daemon=True,
        )
        self._thread.start()
        self._logger.info(f"Reader thread started for {self.ip}")

    def _read_frames(self) -> None:
        """
        Read frames from camera in a loop (runs in background thread).

        Handles reconnection on failures with exponential backoff.
        """
        self._logger.info(f"Frame reader started for {self.ip}")

        retry_count = 0
        consecutive_failures = 0

        while not self._stop_event.is_set():
            # Check connection
            with self._lock:
                cap = self._cap
                if not self._connected or cap is None or not cap.isOpened():
                    self._logger.warning(f"Camera {self.ip} disconnected in thread")
                    self._connected = False

                    # Attempt reconnection
                    if retry_count < CAMERA_SETTINGS.max_retries:
                        retry_count += 1
                        wait_time = min(
                            CAMERA_SETTINGS.retry_delay_base ** retry_count,
                            CAMERA_SETTINGS.max_retry_wait,
                        )
                        self._logger.info(
                            f"Reconnection attempt {retry_count}/{CAMERA_SETTINGS.max_retries} "
                            f"for {self.ip} in {wait_time}s"
                        )

                        if self._stop_event.wait(timeout=wait_time):
                            break

                        if self.connect():
                            retry_count = 0
                            consecutive_failures = 0
                        continue
                    else:
                        self._logger.error(
                            f"Max retries reached for {self.ip}. Stopping thread."
                        )
                        self._state = CameraState.ERROR
                        break

            # Read frame
            try:
                with self._lock:
                    if self._cap is None:
                        continue
                    ret, frame = self._cap.read()

                if ret and frame is not None:
                    consecutive_failures = 0

                    # Add to queue, dropping old frames if full
                    if self._frame_queue.full():
                        try:
                            self._frame_queue.get_nowait()
                        except queue.Empty:
                            pass

                    self._frame_queue.put(frame)
                    time.sleep(0.01)  # Yield CPU
                else:
                    consecutive_failures += 1
                    self._logger.warning(
                        f"Frame read failed for {self.ip} "
                        f"(failure #{consecutive_failures})"
                    )

                    if consecutive_failures >= CAMERA_SETTINGS.consecutive_read_failures_limit:
                        self._logger.error(
                            f"Too many read failures for {self.ip}. Marking disconnected."
                        )
                        self._connected = False
                        with self._lock:
                            if self._cap:
                                self._cap.release()
                                self._cap = None
                    else:
                        time.sleep(0.5)

            except Exception as e:
                self._logger.error(f"Frame read exception for {self.ip}: {e}")
                self._connected = False
                with self._lock:
                    if self._cap:
                        self._cap.release()
                        self._cap = None

        # Cleanup
        with self._lock:
            if self._cap:
                self._cap.release()
                self._cap = None
        self._connected = False
        self._logger.info(f"Frame reader stopped for {self.ip}")

    def get_frame(self) -> Optional[NDArray[np.uint8]]:
        """
        Get the most recent frame from the queue.

        Returns:
            Frame as numpy array or None if no frame available
        """
        try:
            # Check if thread is alive
            if self._thread and not self._thread.is_alive() and self._connected:
                self._logger.warning(
                    f"Thread dead but marked connected for {self.ip}. Disconnecting."
                )
                self.disconnect()
                return None

            return self._frame_queue.get_nowait()

        except queue.Empty:
            return None
        except Exception as e:
            self._logger.error(f"Error getting frame for {self.ip}: {e}")
            return None

    def disconnect(self) -> None:
        """Disconnect camera and release all resources."""
        if self._stop_event.is_set() and not self._connected and self._thread is None:
            return

        self._logger.info(f"Disconnecting camera {self.ip}...")
        self._connected = False
        self._state = CameraState.DISCONNECTED
        self._stop_event.set()

        # Store references for cleanup
        thread_to_join = self._thread
        cap_to_release = self._cap
        self._thread = None
        self._cap = None

        # Wait for thread
        if thread_to_join and thread_to_join.is_alive():
            self._logger.debug(f"Waiting for thread to finish for {self.ip}")
            thread_to_join.join(timeout=2)
            if thread_to_join.is_alive():
                self._logger.warning(f"Thread join timeout for {self.ip}")

        # Release capture
        if cap_to_release:
            try:
                cap_to_release.release()
            except Exception as e:
                self._logger.error(f"Error releasing capture for {self.ip}: {e}")

        # Clear queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break

        self._logger.info(f"Camera {self.ip} disconnected")

    def __repr__(self) -> str:
        """Return string representation of camera."""
        return (
            f"Camera(ip={self.ip!r}, port={self.port}, "
            f"type={self.camera_type!r}, connected={self._connected})"
        )

    def __del__(self) -> None:
        """Cleanup on deletion."""
        try:
            self.disconnect()
        except Exception:
            pass
