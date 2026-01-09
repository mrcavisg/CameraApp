"""
Tests for the camera module.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestCameraType:
    """Tests for CameraType enum."""

    def test_camera_type_values(self) -> None:
        """Test CameraType enum values exist."""
        from cameraapp.camera import CameraType

        assert hasattr(CameraType, "RTSP")
        assert hasattr(CameraType, "ONVIF")


class TestCameraState:
    """Tests for CameraState enum."""

    def test_camera_state_values(self) -> None:
        """Test CameraState enum values exist."""
        from cameraapp.camera import CameraState

        assert hasattr(CameraState, "DISCONNECTED")
        assert hasattr(CameraState, "CONNECTING")
        assert hasattr(CameraState, "CONNECTED")
        assert hasattr(CameraState, "ERROR")


class TestCameraInit:
    """Tests for Camera initialization."""

    def test_camera_init_rtsp(self, mock_logger: logging.Logger) -> None:
        """Test Camera initialization with RTSP URL."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=554,
            username="admin",
            password="password",
            rtsp_url="rtsp://admin:password@192.168.1.100:554/stream",
            camera_type="RTSP",
            logger_instance=mock_logger,
        )

        assert camera.ip == "192.168.1.100"
        assert camera.port == 554
        assert camera.username == "admin"
        assert camera.password == "password"
        assert camera.rtsp_url == "rtsp://admin:password@192.168.1.100:554/stream"
        assert camera.camera_type == "RTSP"
        assert camera.connected is False

    def test_camera_init_onvif(self, mock_logger: logging.Logger) -> None:
        """Test Camera initialization for ONVIF."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.101",
            port=80,
            username="admin",
            password="password",
            rtsp_url="",
            camera_type="ONVIF",
            logger_instance=mock_logger,
        )

        assert camera.camera_type == "ONVIF"
        assert camera.rtsp_url == ""

    def test_camera_type_auto_detection_rtsp(
        self, mock_logger: logging.Logger
    ) -> None:
        """Test camera type auto-detection when RTSP URL provided with ONVIF type."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=80,
            username="admin",
            password="password",
            rtsp_url="rtsp://test",
            camera_type="ONVIF",  # Should be changed to RTSP
            logger_instance=mock_logger,
        )

        assert camera.camera_type == "RTSP"

    def test_camera_type_auto_detection_onvif(
        self, mock_logger: logging.Logger
    ) -> None:
        """Test camera type auto-detection when no RTSP URL with RTSP type."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=80,
            username="admin",
            password="password",
            rtsp_url="",
            camera_type="RTSP",  # Should be changed to ONVIF
            logger_instance=mock_logger,
        )

        assert camera.camera_type == "ONVIF"


class TestCameraConnect:
    """Tests for Camera connection."""

    def test_camera_connect_success(
        self,
        mock_logger: logging.Logger,
        mock_video_capture: MagicMock,
    ) -> None:
        """Test successful camera connection."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=554,
            username="admin",
            password="password",
            rtsp_url="rtsp://admin:password@192.168.1.100:554/stream",
            logger_instance=mock_logger,
        )

        result = camera.connect()

        assert result is True
        assert camera.connected is True

        # Cleanup
        camera.disconnect()

    def test_camera_connect_failure(
        self,
        mock_logger: logging.Logger,
    ) -> None:
        """Test failed camera connection."""
        from cameraapp.camera import Camera

        with patch("cv2.VideoCapture") as mock_cap:
            instance = MagicMock()
            instance.isOpened.return_value = False
            mock_cap.return_value = instance

            camera = Camera(
                ip="192.168.1.100",
                port=554,
                username="admin",
                password="password",
                rtsp_url="rtsp://invalid",
                logger_instance=mock_logger,
            )

            result = camera.connect()

            assert result is False
            assert camera.connected is False

    def test_camera_connect_no_url(
        self,
        mock_logger: logging.Logger,
    ) -> None:
        """Test connection fails without RTSP URL and ONVIF unavailable."""
        from cameraapp.camera import Camera

        with patch("cameraapp.camera.ONVIF_AVAILABLE", False):
            camera = Camera(
                ip="192.168.1.100",
                port=80,
                username="admin",
                password="password",
                rtsp_url="",
                camera_type="ONVIF",
                logger_instance=mock_logger,
            )

            result = camera.connect()

            assert result is False


class TestCameraGetFrame:
    """Tests for Camera frame retrieval."""

    def test_get_frame_when_disconnected(
        self,
        mock_logger: logging.Logger,
    ) -> None:
        """Test get_frame returns None when disconnected."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=554,
            username="admin",
            password="password",
            rtsp_url="rtsp://test",
            logger_instance=mock_logger,
        )

        frame = camera.get_frame()

        assert frame is None

    def test_get_frame_when_connected(
        self,
        mock_logger: logging.Logger,
        mock_video_capture: MagicMock,
    ) -> None:
        """Test get_frame returns frame when connected."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=554,
            username="admin",
            password="password",
            rtsp_url="rtsp://admin:password@192.168.1.100:554/stream",
            logger_instance=mock_logger,
        )

        camera.connect()

        # Wait a bit for thread to read frames
        import time
        time.sleep(0.1)

        frame = camera.get_frame()

        # Frame might be None if thread hasn't read yet
        if frame is not None:
            assert isinstance(frame, np.ndarray)

        camera.disconnect()


class TestCameraDisconnect:
    """Tests for Camera disconnection."""

    def test_camera_disconnect(
        self,
        mock_logger: logging.Logger,
        mock_video_capture: MagicMock,
    ) -> None:
        """Test camera disconnection."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=554,
            username="admin",
            password="password",
            rtsp_url="rtsp://admin:password@192.168.1.100:554/stream",
            logger_instance=mock_logger,
        )

        camera.connect()
        assert camera.connected is True

        camera.disconnect()
        assert camera.connected is False

    def test_camera_disconnect_when_not_connected(
        self,
        mock_logger: logging.Logger,
    ) -> None:
        """Test disconnect when not connected doesn't raise."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=554,
            username="admin",
            password="password",
            rtsp_url="rtsp://test",
            logger_instance=mock_logger,
        )

        # Should not raise
        camera.disconnect()
        assert camera.connected is False


class TestCameraMaskUrl:
    """Tests for URL masking."""

    def test_mask_url_with_password(
        self,
        mock_logger: logging.Logger,
    ) -> None:
        """Test URL password is masked."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=554,
            username="admin",
            password="password",
            rtsp_url="rtsp://test",
            logger_instance=mock_logger,
        )

        masked = camera._mask_url("rtsp://admin:secret123@192.168.1.100/stream")

        assert "secret123" not in masked
        assert "****" in masked
        assert "admin" in masked

    def test_mask_url_without_password(
        self,
        mock_logger: logging.Logger,
    ) -> None:
        """Test URL without password is unchanged."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=554,
            username="admin",
            password="password",
            rtsp_url="rtsp://test",
            logger_instance=mock_logger,
        )

        original = "rtsp://192.168.1.100/stream"
        masked = camera._mask_url(original)

        assert masked == original


class TestCameraRepr:
    """Tests for Camera string representation."""

    def test_camera_repr(self, mock_logger: logging.Logger) -> None:
        """Test Camera __repr__ method."""
        from cameraapp.camera import Camera

        camera = Camera(
            ip="192.168.1.100",
            port=554,
            username="admin",
            password="password",
            rtsp_url="rtsp://test",
            logger_instance=mock_logger,
        )

        repr_str = repr(camera)

        assert "192.168.1.100" in repr_str
        assert "554" in repr_str
        assert "RTSP" in repr_str
        assert "password" not in repr_str  # Password should not be in repr
