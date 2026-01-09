"""
CameraApp - Professional IP Camera Management System.

A desktop application for managing and monitoring IP cameras
using ONVIF and RTSP protocols.

Author: Caio Vinicius (CFA TECH)
License: MIT
"""

__version__ = "1.0.0"
__author__ = "Caio Vinicius"
__email__ = "contact@cfatech.com"

from cameraapp.app import CameraApp
from cameraapp.camera import Camera

__all__ = ["CameraApp", "Camera", "__version__"]
