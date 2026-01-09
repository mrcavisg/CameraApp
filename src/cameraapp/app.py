"""
Main application module for CameraApp.

Provides the GUI interface for camera management and video display.
"""

from __future__ import annotations

import logging
import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageTk

from cameraapp.camera import Camera, ONVIF_AVAILABLE
from cameraapp.config import APP_NAME, LOGGER_NAME, UI_SETTINGS
from cameraapp.utils import center_window, load_cameras, save_cameras
from cameraapp.scanner import NetworkScanner, DiscoveredCamera, get_local_network

# ONVIF discovery imports
try:
    from wsdiscovery import WSDiscovery

    WSDISCOVERY_AVAILABLE = True
except ImportError:
    WSDISCOVERY_AVAILABLE = False

logger = logging.getLogger(LOGGER_NAME)


class ONVIFQName:
    """QName wrapper for WS-Discovery ONVIF type filtering."""

    def __init__(self, namespace: str, local_part: str) -> None:
        """Initialize QName with namespace and local part."""
        self.namespace = namespace
        self.local_part = local_part

    def getNamespace(self) -> str:
        """Return the namespace."""
        return self.namespace

    def getLocalname(self) -> str:
        """Return the local name."""
        return self.local_part

    def getNamespacePrefix(self) -> Optional[str]:
        """Return the namespace prefix (None for default)."""
        return None

    def getFullname(self) -> str:
        """Return the full qualified name."""
        return f"{{{self.namespace}}}{self.local_part}"


class CameraApp:
    """
    Main application class for the camera monitoring system.

    Provides a GUI for managing IP cameras, displaying video feeds,
    and configuring camera connections.

    Attributes:
        root: The main tkinter window
        cameras: List of connected cameras
        running: Whether the application is running
    """

    def __init__(self, root: tk.Tk, app_logger: logging.Logger) -> None:
        """
        Initialize the CameraApp.

        Args:
            root: The main tkinter window
            app_logger: Logger instance for the application
        """
        self._logger = app_logger
        self._logger.info("Initializing CameraApp...")

        self.root = root
        self.root.title(f"{APP_NAME} by CFA TECH")
        self.root.geometry(
            f"{UI_SETTINGS.default_window_width}x{UI_SETTINGS.default_window_height}"
        )
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # State
        self.cameras: list[Camera] = []
        self._labels: list[tk.Label] = []
        self._aspect_ratios: list[str] = []
        self._camera_list_window: Optional[tk.Toplevel] = None
        self._camera_treeview: Optional[ttk.Treeview] = None
        self._empty_frame_counts: dict[str, int] = {}  # Track empty frames per camera
        self.running = True

        # Setup UI
        self._setup_style()
        self._create_menu()
        self._create_widgets()

        # Center window
        self.root.update_idletasks()
        center_window(self.root)

    def _setup_style(self) -> None:
        """Configure ttk style."""
        style = ttk.Style()
        style.theme_use("clam")

    def _create_menu(self) -> None:
        """Create the application menu bar."""
        try:
            menubar = tk.Menu(self.root)
            self.root.config(menu=menubar)

            options_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Options", menu=options_menu)

            options_menu.add_command(
                label="Manage Cameras",
                command=self._open_camera_manager,
            )
            options_menu.add_separator()
            options_menu.add_command(label="Minimize", command=self._minimize)
            options_menu.add_command(label="Exit", command=self._on_close)

            self._logger.info("Menu created")
        except Exception as e:
            self._logger.error(f"Error creating menu: {e}", exc_info=True)

    def _create_widgets(self) -> None:
        """Create main window widgets."""
        try:
            self._frame_container = tk.Frame(self.root)
            self._frame_container.pack(expand=True, fill=tk.BOTH)

            self._load_cameras()
            self._start_cameras()
            self._create_video_labels()
            self._update_frames()

            self._logger.info("Widgets created and cameras started")
        except Exception as e:
            self._logger.error(f"Error creating widgets: {e}", exc_info=True)
            messagebox.showerror(
                "Initialization Error",
                f"Failed to initialize interface:\n{e}",
            )
            self._on_close()

    def _load_cameras(self) -> None:
        """Load cameras from configuration file."""
        try:
            loaded_cameras = load_cameras(self._logger)
            self.cameras = [cam for cam in loaded_cameras if isinstance(cam, Camera)]
            self._logger.info(f"{len(self.cameras)} cameras loaded")
        except Exception as e:
            self._logger.error(f"Error loading cameras: {e}", exc_info=True)
            self.cameras = []

    def _start_cameras(self) -> None:
        """Connect all loaded cameras."""
        try:
            self._logger.info("Starting camera connections...")
            connected = 0

            for camera in self.cameras:
                if not camera.connected:
                    if camera.connect():
                        connected += 1
                    else:
                        self._logger.warning(
                            f"Failed to connect: IP={camera.ip}, "
                            f"RTSP={camera.rtsp_url}"
                        )
                else:
                    connected += 1

            self._logger.info(f"{connected}/{len(self.cameras)} cameras connected")
        except Exception as e:
            self._logger.error(f"Error starting cameras: {e}", exc_info=True)

    def _create_video_labels(self) -> None:
        """Create video display labels for each camera."""
        try:
            # Clear existing labels
            for label in self._labels:
                if label.winfo_exists():
                    label.destroy()

            self._labels = []
            self._aspect_ratios = []

            num_cameras = len(self.cameras)
            display_cells = max(num_cameras, 1)
            cols = UI_SETTINGS.grid_columns
            rows = (display_cells + cols - 1) // cols

            # Configure grid
            for i in range(rows):
                self._frame_container.grid_rowconfigure(i, weight=1)
            for i in range(cols):
                self._frame_container.grid_columnconfigure(i, weight=1)

            # Create labels
            for i in range(num_cameras):
                label = tk.Label(
                    self._frame_container,
                    bg="black",
                    text=f"Camera {i + 1}",
                    fg="white",
                )
                row = i // cols
                col = i % cols
                label.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)

                self._labels.append(label)
                self._aspect_ratios.append(UI_SETTINGS.default_aspect_ratio)
                self._add_context_menu(label, i)

            self._logger.info(f"Created {num_cameras} video labels")

            if num_cameras == 0:
                no_cam_label = tk.Label(
                    self._frame_container,
                    text="No cameras configured",
                    bg="black",
                    fg="white",
                )
                no_cam_label.grid(row=0, column=0, columnspan=cols, sticky="nsew")

        except Exception as e:
            self._logger.error(f"Error creating video labels: {e}", exc_info=True)

    def _add_context_menu(self, label: tk.Label, index: int) -> None:
        """Add aspect ratio context menu to a label."""
        try:
            menu = tk.Menu(label, tearoff=0)
            menu.add_command(
                label="4:3",
                command=lambda: self._set_aspect_ratio(index, "4:3"),
            )
            menu.add_command(
                label="16:9",
                command=lambda: self._set_aspect_ratio(index, "16:9"),
            )
            menu.add_command(
                label="Fit",
                command=lambda: self._set_aspect_ratio(index, "fit"),
            )
            label.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))
        except Exception as e:
            self._logger.error(f"Error adding context menu: {e}")

    def _set_aspect_ratio(self, index: int, ratio: str) -> None:
        """Set aspect ratio for a camera display."""
        if 0 <= index < len(self._aspect_ratios):
            self._aspect_ratios[index] = ratio
            self._logger.info(f"Aspect ratio for camera {index} set to {ratio}")

    def _resize_frame(
        self,
        frame: NDArray[np.uint8],
        label: tk.Label,
        aspect_ratio: str,
    ) -> Optional[NDArray[np.uint8]]:
        """
        Resize frame to fit label with specified aspect ratio.

        Args:
            frame: Input frame
            label: Target label widget
            aspect_ratio: Aspect ratio ("4:3", "16:9", or "fit")

        Returns:
            Resized frame or None on error
        """
        try:
            label_width = label.winfo_width()
            label_height = label.winfo_height()

            if label_width <= 1 or label_height <= 1:
                return None

            frame_height, frame_width = frame.shape[:2]
            if frame_height == 0 or frame_width == 0:
                return None

            # Determine interpolation
            interpolation = cv2.INTER_AREA

            # Handle "fit" mode
            if aspect_ratio == "fit":
                if label_width > frame_width:
                    interpolation = cv2.INTER_LINEAR
                return cv2.resize(
                    frame,
                    (label_width, label_height),
                    interpolation=interpolation,
                )

            # Calculate target ratio
            target_ratio = {"4:3": 4 / 3, "16:9": 16 / 9}.get(aspect_ratio)
            if target_ratio is None:
                return cv2.resize(
                    frame,
                    (label_width, label_height),
                    interpolation=interpolation,
                )

            # Calculate new dimensions maintaining ratio
            new_width = label_width
            new_height = int(new_width / target_ratio)

            if new_height > label_height:
                new_height = label_height
                new_width = int(new_height * target_ratio)

            new_width = max(1, new_width)
            new_height = max(1, new_height)

            if new_width > frame_width:
                interpolation = cv2.INTER_LINEAR

            resized = cv2.resize(
                frame,
                (new_width, new_height),
                interpolation=interpolation,
            )

            # Add padding if needed
            if new_width != label_width or new_height != label_height:
                top = (label_height - new_height) // 2
                left = (label_width - new_width) // 2
                output = np.zeros((label_height, label_width, 3), dtype=np.uint8)
                output[top : top + new_height, left : left + new_width] = resized
                return output

            return resized

        except Exception as e:
            self._logger.error(f"Error resizing frame: {e}", exc_info=True)
            return None

    def _update_frames(self) -> None:
        """Update video frames for all cameras (called periodically)."""
        try:
            if not self.running:
                return

            num_labels = len(self._labels)
            num_cameras = len(self.cameras)

            # Recreate labels if mismatch
            if num_labels != num_cameras:
                self._logger.warning(
                    f"Label/camera mismatch ({num_labels}/{num_cameras}). Recreating."
                )
                self._create_video_labels()
                self.root.after(UI_SETTINGS.frame_update_interval, self._update_frames)
                return

            for i in range(num_cameras):
                camera = self.cameras[i]
                label = self._labels[i]

                if not label.winfo_exists():
                    continue

                if not isinstance(camera, Camera):
                    label.config(image="", text=f"Error {i}", fg="red")
                    continue

                frame = None
                if camera.connected:
                    frame = camera.get_frame()

                if frame is not None:
                    # Reset empty frame counter on successful frame
                    self._empty_frame_counts[camera.ip] = 0

                    aspect = (
                        self._aspect_ratios[i]
                        if 0 <= i < len(self._aspect_ratios)
                        else "fit"
                    )
                    resized = self._resize_frame(frame, label, aspect)

                    if resized is not None:
                        try:
                            rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                            img = Image.fromarray(rgb_frame)
                            imgtk = ImageTk.PhotoImage(image=img)
                            label.config(image=imgtk, text="")
                            label.image = imgtk  # Keep reference
                        except Exception as e:
                            self._logger.error(f"Error displaying frame: {e}")
                            label.config(image="", text="Display Error", fg="red")
                    else:
                        label.config(image="", text="Resize Error", fg="red")
                else:
                    # Track consecutive empty frames before marking disconnected
                    empty_count = self._empty_frame_counts.get(camera.ip, 0) + 1
                    self._empty_frame_counts[camera.ip] = empty_count

                    # Only mark disconnected after 100 consecutive empty frames (~3 seconds)
                    if camera.connected and empty_count >= 100:
                        self._logger.warning(f"Camera {camera.ip} stopped sending frames")
                        camera.connected = False

                    if not camera.connected:
                        if label.cget("text") != "Disconnected":
                            label.config(image="", text="Disconnected", fg="orange")
                        self._update_treeview_status(i, "Disconnected")

            if self.running:
                self.root.after(UI_SETTINGS.frame_update_interval, self._update_frames)

        except Exception as e:
            self._logger.error(f"Error in frame update loop: {e}", exc_info=True)
            if self.running:
                self.root.after(
                    UI_SETTINGS.frame_update_interval * 10,
                    self._update_frames,
                )

    def _update_treeview_status(self, index: int, status: str) -> None:
        """Update camera status in the treeview."""
        if not self._camera_list_window or not self._camera_list_window.winfo_exists():
            return
        if not self._camera_treeview:
            return

        try:
            children = self._camera_treeview.get_children()
            if 0 <= index < len(children):
                item_id = children[index]
                current_values = list(self._camera_treeview.item(item_id)["values"])

                while len(current_values) <= 5:
                    current_values.append("")

                if current_values[5] != status:
                    current_values[5] = status
                    self._camera_treeview.item(item_id, values=tuple(current_values))

        except tk.TclError:
            pass
        except Exception as e:
            self._logger.error(f"Error updating treeview status: {e}")

    # ==================== Camera Manager Window ====================

    def _open_camera_manager(self) -> None:
        """Open the camera management window."""
        try:
            if self._camera_list_window and self._camera_list_window.winfo_exists():
                self._camera_list_window.lift()
                return

            self._camera_list_window = tk.Toplevel(self.root)
            self._camera_list_window.title("Manage Cameras")
            self._camera_list_window.geometry("800x400")
            center_window(self._camera_list_window)

            # Buttons
            button_frame = ttk.Frame(self._camera_list_window, padding="5")
            button_frame.pack(side=tk.TOP, fill=tk.X)

            ttk.Button(
                button_frame,
                text="Add ONVIF",
                command=self._add_onvif_dialog,
            ).pack(side=tk.LEFT, padx=2)

            ttk.Button(
                button_frame,
                text="Add RTSP",
                command=self._add_rtsp_dialog,
            ).pack(side=tk.LEFT, padx=2)

            ttk.Button(
                button_frame,
                text="Edit",
                command=self._edit_camera_dialog,
            ).pack(side=tk.LEFT, padx=2)

            ttk.Button(
                button_frame,
                text="Remove",
                command=self._remove_camera,
            ).pack(side=tk.LEFT, padx=2)

            if WSDISCOVERY_AVAILABLE:
                ttk.Button(
                    button_frame,
                    text="Discover ONVIF",
                    command=self._discover_cameras,
                ).pack(side=tk.LEFT, padx=2)

            ttk.Button(
                button_frame,
                text="Scan Network",
                command=self._open_network_scan_dialog,
            ).pack(side=tk.LEFT, padx=2)

            ttk.Button(
                button_frame,
                text="Close",
                command=self._close_camera_manager,
            ).pack(side=tk.RIGHT, padx=5)

            # Camera list
            list_frame = ttk.Frame(self._camera_list_window, padding="5")
            list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            columns = ("type", "ip", "port", "username", "rtsp_url", "status")
            self._camera_treeview = ttk.Treeview(
                list_frame,
                columns=columns,
                show="headings",
                selectmode="browse",
            )

            self._camera_treeview.heading("type", text="Type")
            self._camera_treeview.column("type", width=60, anchor=tk.W)
            self._camera_treeview.heading("ip", text="IP")
            self._camera_treeview.column("ip", width=120, anchor=tk.W)
            self._camera_treeview.heading("port", text="Port")
            self._camera_treeview.column("port", width=50, anchor=tk.CENTER)
            self._camera_treeview.heading("username", text="User")
            self._camera_treeview.column("username", width=100, anchor=tk.W)
            self._camera_treeview.heading("rtsp_url", text="RTSP URL")
            self._camera_treeview.column("rtsp_url", width=300, anchor=tk.W)
            self._camera_treeview.heading("status", text="Status")
            self._camera_treeview.column("status", width=100, anchor=tk.CENTER)

            scrollbar = ttk.Scrollbar(
                list_frame,
                orient=tk.VERTICAL,
                command=self._camera_treeview.yview,
            )
            self._camera_treeview.configure(yscroll=scrollbar.set)

            self._camera_treeview.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            list_frame.grid_rowconfigure(0, weight=1)
            list_frame.grid_columnconfigure(0, weight=1)

            self._populate_camera_list()
            self._camera_list_window.protocol(
                "WM_DELETE_WINDOW",
                self._close_camera_manager,
            )

            self._logger.info("Camera manager window opened")

        except Exception as e:
            self._logger.error(f"Error opening camera manager: {e}", exc_info=True)

    def _populate_camera_list(self) -> None:
        """Populate the camera list treeview."""
        if not self._camera_treeview:
            return

        try:
            for item in self._camera_treeview.get_children():
                self._camera_treeview.delete(item)

            for cam in self.cameras:
                if not isinstance(cam, Camera):
                    continue

                camera_type = "RTSP" if cam.rtsp_url else "ONVIF"
                status = "Connected" if cam.connected else "Disconnected"
                tag = "connected" if cam.connected else "disconnected"

                values = (
                    camera_type,
                    cam.ip,
                    str(cam.port),
                    cam.username or "-",
                    cam.rtsp_url or "-",
                    status,
                )
                self._camera_treeview.insert("", tk.END, values=values, tags=(tag,))

            self._camera_treeview.tag_configure("disconnected", foreground="red")
            self._camera_treeview.tag_configure("connected", foreground="green")

        except Exception as e:
            self._logger.error(f"Error populating camera list: {e}", exc_info=True)

    def _close_camera_manager(self) -> None:
        """Close the camera manager window."""
        try:
            if self._camera_list_window and self._camera_list_window.winfo_exists():
                self._camera_list_window.destroy()
            self._camera_list_window = None
            self._camera_treeview = None
            self._logger.info("Camera manager closed")
        except Exception as e:
            self._logger.error(f"Error closing camera manager: {e}")

    # ==================== Camera Dialogs ====================

    def _add_onvif_dialog(self) -> None:
        """Show dialog to add an ONVIF camera."""
        if not ONVIF_AVAILABLE:
            messagebox.showerror("Error", "ONVIF library not available")
            return

        parent = self._camera_list_window or self.root
        dialog = tk.Toplevel(parent)
        dialog.title("Add ONVIF Camera")
        dialog.geometry("300x200")
        dialog.transient(parent)
        dialog.grab_set()
        center_window(dialog)

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        # IP
        ttk.Label(frame, text="IP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ip_entry = ttk.Entry(frame, width=25)
        ip_entry.grid(row=0, column=1, padx=5, pady=5)

        # Port
        ttk.Label(frame, text="Port:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        port_entry = ttk.Entry(frame, width=10)
        port_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        port_entry.insert(0, "80")

        # Username
        ttk.Label(frame, text="User:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        user_entry = ttk.Entry(frame, width=25)
        user_entry.grid(row=2, column=1, padx=5, pady=5)

        # Password
        ttk.Label(frame, text="Password:").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=5
        )
        pass_entry = ttk.Entry(frame, width=25, show="*")
        pass_entry.grid(row=3, column=1, padx=5, pady=5)

        def save() -> None:
            ip = ip_entry.get().strip()
            port_str = port_entry.get().strip()
            username = user_entry.get().strip()
            password = pass_entry.get()

            if not ip or not port_str or not username:
                messagebox.showerror(
                    "Error",
                    "IP, Port, and User are required",
                    parent=dialog,
                )
                return

            try:
                port = int(port_str)
            except ValueError:
                messagebox.showerror("Error", "Invalid port", parent=dialog)
                return

            camera = Camera(ip, port, username, password, logger_instance=self._logger)
            if camera.connect(timeout_open=10000):
                self.cameras.append(camera)
                self._populate_camera_list()
                save_cameras(self.cameras, self._logger)
                self._create_video_labels()
                dialog.destroy()
                self._logger.info(f"ONVIF camera added: {ip}")
            else:
                messagebox.showerror(
                    "Error",
                    f"Failed to connect to ONVIF camera {ip}",
                    parent=dialog,
                )

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        dialog.bind("<Return>", lambda e: save())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        ip_entry.focus_set()

    def _add_rtsp_dialog(self) -> None:
        """Show dialog to add an RTSP camera."""
        parent = self._camera_list_window or self.root
        dialog = tk.Toplevel(parent)
        dialog.title("Add RTSP Camera")
        dialog.geometry("450x150")
        dialog.transient(parent)
        dialog.grab_set()
        center_window(dialog)

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(frame, text="RTSP URL:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5
        )
        rtsp_entry = ttk.Entry(frame, width=50)
        rtsp_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        ttk.Label(frame, text="Ex: rtsp://user:pass@ip:port/stream").grid(
            row=1, column=1, sticky=tk.W, padx=5
        )

        def save() -> None:
            rtsp_url = rtsp_entry.get().strip()

            if not rtsp_url.lower().startswith("rtsp://"):
                messagebox.showerror("Error", "Invalid RTSP URL", parent=dialog)
                return

            # Parse URL
            ip, port, user, password = "N/A", 554, "", ""
            match = re.match(
                r"rtsp://(?:([^:]+)(?::([^@]+))?@)?([^:/]+)(?::(\d+))?(?:/.*)?",
                rtsp_url,
            )

            if match:
                user = match.group(1) or ""
                password = match.group(2) or ""
                ip = match.group(3)
                port = int(match.group(4) or 554)
            else:
                messagebox.showerror(
                    "Error",
                    "Could not parse RTSP URL",
                    parent=dialog,
                )
                return

            camera = Camera(
                ip, port, user, password, rtsp_url, logger_instance=self._logger
            )
            if camera.connect():
                self.cameras.append(camera)
                self._populate_camera_list()
                save_cameras(self.cameras, self._logger)
                self._create_video_labels()
                dialog.destroy()
                self._logger.info(f"RTSP camera added: {rtsp_url}")
            else:
                messagebox.showerror(
                    "Error",
                    f"Failed to connect to RTSP:\n{rtsp_url}",
                    parent=dialog,
                )

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        dialog.bind("<Return>", lambda e: save())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        rtsp_entry.focus_set()

    def _edit_camera_dialog(self) -> None:
        """Show dialog to edit selected camera."""
        if not self._camera_treeview:
            return

        selected = self._camera_treeview.selection()
        if not selected:
            messagebox.showwarning(
                "Warning",
                "Select a camera to edit",
                parent=self._camera_list_window,
            )
            return

        try:
            index = self._camera_treeview.index(selected[0])
            camera = self.cameras[index]
        except (IndexError, Exception) as e:
            messagebox.showerror(
                "Error",
                f"Could not find camera: {e}",
                parent=self._camera_list_window,
            )
            return

        camera_type = "RTSP" if camera.rtsp_url else "ONVIF"
        parent = self._camera_list_window or self.root
        dialog = tk.Toplevel(parent)
        dialog.title(f"Edit Camera ({camera_type})")
        dialog.transient(parent)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        if camera_type == "ONVIF":
            if not ONVIF_AVAILABLE:
                messagebox.showerror("Error", "ONVIF library not available")
                dialog.destroy()
                return

            dialog.geometry("300x200")

            ttk.Label(frame, text="IP:").grid(
                row=0, column=0, sticky=tk.W, padx=5, pady=5
            )
            ip_entry = ttk.Entry(frame, width=25)
            ip_entry.grid(row=0, column=1, padx=5, pady=5)
            ip_entry.insert(0, camera.ip)

            ttk.Label(frame, text="Port:").grid(
                row=1, column=0, sticky=tk.W, padx=5, pady=5
            )
            port_entry = ttk.Entry(frame, width=10)
            port_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
            port_entry.insert(0, str(camera.port))

            ttk.Label(frame, text="User:").grid(
                row=2, column=0, sticky=tk.W, padx=5, pady=5
            )
            user_entry = ttk.Entry(frame, width=25)
            user_entry.grid(row=2, column=1, padx=5, pady=5)
            user_entry.insert(0, camera.username)

            ttk.Label(frame, text="Password:").grid(
                row=3, column=0, sticky=tk.W, padx=5, pady=5
            )
            pass_entry = ttk.Entry(frame, width=25, show="*")
            pass_entry.grid(row=3, column=1, padx=5, pady=5)
            pass_entry.insert(0, camera.password)

            def save_onvif() -> None:
                camera.disconnect()
                camera.ip = ip_entry.get().strip()
                camera.port = int(port_entry.get().strip())
                camera.username = user_entry.get().strip()
                camera.password = pass_entry.get()
                camera.rtsp_url = ""

                if camera.connect(timeout_open=10000):
                    self._populate_camera_list()
                    save_cameras(self.cameras, self._logger)
                    self._create_video_labels()
                    dialog.destroy()
                else:
                    messagebox.showerror(
                        "Error",
                        f"Failed to reconnect to {camera.ip}",
                        parent=dialog,
                    )

            save_func = save_onvif
            focus_widget = ip_entry

        else:  # RTSP
            dialog.geometry("450x150")

            ttk.Label(frame, text="RTSP URL:").grid(
                row=0, column=0, sticky=tk.W, padx=5, pady=5
            )
            rtsp_entry = ttk.Entry(frame, width=50)
            rtsp_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
            rtsp_entry.insert(0, camera.rtsp_url)
            frame.grid_columnconfigure(1, weight=1)

            def save_rtsp() -> None:
                rtsp_url = rtsp_entry.get().strip()
                if not rtsp_url.lower().startswith("rtsp://"):
                    messagebox.showerror("Error", "Invalid RTSP URL", parent=dialog)
                    return

                match = re.match(
                    r"rtsp://(?:([^:]+)(?::([^@]+))?@)?([^:/]+)(?::(\d+))?(?:/.*)?",
                    rtsp_url,
                )
                if not match:
                    messagebox.showerror(
                        "Error",
                        "Could not parse RTSP URL",
                        parent=dialog,
                    )
                    return

                camera.disconnect()
                camera.username = match.group(1) or ""
                camera.password = match.group(2) or ""
                camera.ip = match.group(3)
                camera.port = int(match.group(4) or 554)
                camera.rtsp_url = rtsp_url

                if camera.connect():
                    self._populate_camera_list()
                    save_cameras(self.cameras, self._logger)
                    self._create_video_labels()
                    dialog.destroy()
                else:
                    messagebox.showerror(
                        "Error",
                        f"Failed to reconnect:\n{rtsp_url}",
                        parent=dialog,
                    )

            save_func = save_rtsp
            focus_widget = rtsp_entry

        center_window(dialog)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Save", command=save_func).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        dialog.bind("<Return>", lambda e: save_func())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        focus_widget.focus_set()

    def _remove_camera(self) -> None:
        """Remove selected camera."""
        if not self._camera_treeview:
            return

        selected = self._camera_treeview.selection()
        if not selected:
            messagebox.showwarning(
                "Warning",
                "Select a camera to remove",
                parent=self._camera_list_window,
            )
            return

        try:
            index = self._camera_treeview.index(selected[0])
            camera = self.cameras[index]
        except (IndexError, Exception) as e:
            messagebox.showerror(
                "Error",
                f"Could not find camera: {e}",
                parent=self._camera_list_window,
            )
            return

        if messagebox.askyesno(
            "Confirm Removal",
            f"Remove camera {camera.ip}?",
            parent=self._camera_list_window,
        ):
            camera.disconnect()
            del self.cameras[index]
            self._camera_treeview.delete(selected[0])
            save_cameras(self.cameras, self._logger)
            self._create_video_labels()
            self._logger.info(f"Camera {camera.ip} removed")

    def _discover_cameras(self) -> None:
        """Discover ONVIF cameras on the network."""
        if not WSDISCOVERY_AVAILABLE:
            messagebox.showerror("Error", "WS-Discovery not available")
            return

        if not ONVIF_AVAILABLE:
            messagebox.showerror("Error", "ONVIF library not available")
            return

        wsd = None
        status_label = None

        try:
            if not self._camera_list_window or not self._camera_list_window.winfo_exists():
                messagebox.showerror("Error", "Open camera manager first")
                return

            self._logger.info("Starting ONVIF camera discovery...")

            status_label = ttk.Label(
                self._camera_list_window,
                text="Searching for ONVIF cameras...",
            )
            status_label.pack(side=tk.BOTTOM, fill=tk.X)
            self._camera_list_window.update_idletasks()

            # Clear previously discovered items
            if self._camera_treeview:
                items_to_remove = []
                for item_id in self._camera_treeview.get_children():
                    values = self._camera_treeview.item(item_id, "values")
                    if values and len(values) >= 6 and str(values[5]).startswith("Discovered"):
                        items_to_remove.append(item_id)
                for item_id in items_to_remove:
                    self._camera_treeview.delete(item_id)

            # WS-Discovery
            wsd = WSDiscovery()
            wsd.start()

            type_filter = ONVIFQName(
                "http://www.onvif.org/ver10/network/wsdl",
                "NetworkVideoTransmitter",
            )
            services = wsd.searchServices(types=[type_filter], timeout=10)
            wsd.stop()

            discovered = []
            existing_ips = {cam.ip for cam in self.cameras if isinstance(cam, Camera)}

            for service in services:
                ip = None
                xaddrs = service.getXAddrs()

                if xaddrs:
                    for xaddr in xaddrs:
                        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", xaddr)
                        if match:
                            potential_ip = match.group(1)
                            if potential_ip != "127.0.0.1" or len(xaddrs) == 1:
                                ip = potential_ip
                                break

                if not ip:
                    try:
                        epr = service.getEPR()
                        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", epr)
                        if match:
                            ip = match.group(1)
                    except Exception:
                        pass

                if not ip:
                    continue
                if ip in existing_ips or ip in [d["ip"] for d in discovered]:
                    continue

                discovered.append({
                    "type": "ONVIF",
                    "ip": ip,
                    "port": 80,
                    "username": "",
                    "rtsp_url": "",
                    "status": "Discovered",
                })
                self._logger.info(f"Discovered ONVIF camera: {ip}")

            # Add to treeview
            added = 0
            if self._camera_treeview:
                for cam_info in discovered:
                    self._camera_treeview.insert(
                        "",
                        tk.END,
                        values=(
                            cam_info["type"],
                            cam_info["ip"],
                            cam_info["port"],
                            cam_info["username"],
                            cam_info["rtsp_url"],
                            cam_info["status"],
                        ),
                        tags=("discovered",),
                    )
                    added += 1
                self._camera_treeview.tag_configure("discovered", foreground="blue")

            if status_label and status_label.winfo_exists():
                status_label.destroy()

            self._logger.info(f"Discovery complete. Found {added} new cameras.")
            messagebox.showinfo(
                "Discovery Complete",
                f"Found {added} new ONVIF cameras",
                parent=self._camera_list_window,
            )

        except Exception as e:
            if status_label and status_label.winfo_exists():
                status_label.destroy()
            self._logger.error(f"Discovery error: {e}", exc_info=True)
            parent = self._camera_list_window or self.root
            messagebox.showerror("Discovery Error", f"Error: {e}", parent=parent)

        finally:
            if wsd is not None:
                try:
                    if hasattr(wsd, "stop") and callable(wsd.stop):
                        wsd.stop()
                except Exception:
                    pass

    # ==================== Network Scanner ====================

    def _open_network_scan_dialog(self) -> None:
        """Open network scan dialog to find cameras."""
        import threading

        parent = self._camera_list_window or self.root
        dialog = tk.Toplevel(parent)
        dialog.title("Scan Network for Cameras")
        dialog.geometry("600x500")
        dialog.transient(parent)
        dialog.grab_set()
        center_window(dialog)

        # Main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # IP Range input
        input_frame = ttk.LabelFrame(main_frame, text="Scan Settings", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(input_frame, text="IP Range:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ip_entry = ttk.Entry(input_frame, width=30)
        ip_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # Auto-detect network
        local_net = get_local_network()
        if local_net:
            ip_entry.insert(0, local_net)
        else:
            ip_entry.insert(0, "192.168.0.0/24")

        ttk.Label(input_frame, text="Ex: 192.168.0.0/24 ou 192.168.0.1-254").grid(
            row=1, column=1, sticky=tk.W, padx=5
        )

        # Options
        onvif_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            input_frame, text="Include ONVIF Discovery", variable=onvif_var
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Progress
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(
            progress_frame, variable=progress_var, maximum=100
        )
        progress_bar.pack(fill=tk.X, pady=5)

        status_label = ttk.Label(progress_frame, text="Ready to scan")
        status_label.pack(anchor=tk.W)

        # Store discovered cameras
        discovered: list[DiscoveredCamera] = []
        scanner: Optional[NetworkScanner] = None
        scan_thread: Optional[threading.Thread] = None

        def update_progress(current: int, total: int, message: str) -> None:
            """Update progress from scanner (called from thread)."""
            try:
                if total > 0:
                    pct = (current / total) * 100
                    progress_var.set(pct)
                status_label.config(text=message)
                dialog.update_idletasks()
            except Exception:
                pass

        def run_scan() -> None:
            """Run scan in background thread."""
            nonlocal discovered, scanner

            try:
                scanner = NetworkScanner(
                    timeout=1.0,
                    max_workers=100,
                    progress_callback=lambda c, t, m: dialog.after(
                        0, lambda: update_progress(c, t, m)
                    ),
                )

                ip_range = ip_entry.get().strip()
                include_onvif = onvif_var.get()

                discovered = scanner.full_scan(
                    ip_range=ip_range,
                    include_onvif=include_onvif,
                )

                # Update UI in main thread
                dialog.after(0, display_results)

            except Exception as e:
                dialog.after(
                    0,
                    lambda: messagebox.showerror("Scan Error", str(e), parent=dialog),
                )
            finally:
                dialog.after(0, lambda: scan_btn.config(state=tk.NORMAL))
                dialog.after(0, lambda: stop_btn.config(state=tk.DISABLED))

        def display_results() -> None:
            """Display scan results in treeview."""
            # Clear previous results
            for item in results_tree.get_children():
                results_tree.delete(item)

            for cam in discovered:
                ports_str = ", ".join(str(p) for p in cam.ports[:4])
                rtsp_url = cam.get_suggested_rtsp_url()
                results_tree.insert(
                    "",
                    tk.END,
                    values=(cam.ip, ports_str, cam.manufacturer, rtsp_url),
                )

            status_label.config(text=f"Scan complete: {len(discovered)} camera(s) found")
            progress_var.set(100)

        def start_scan() -> None:
            """Start the network scan."""
            nonlocal scan_thread

            scan_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
            progress_var.set(0)

            scan_thread = threading.Thread(target=run_scan, daemon=True)
            scan_thread.start()

        def stop_scan() -> None:
            """Stop the running scan."""
            if scanner:
                scanner.stop()
            stop_btn.config(state=tk.DISABLED)
            status_label.config(text="Stopping scan...")

        def add_selected() -> None:
            """Add selected camera to the app."""
            selected = results_tree.selection()
            if not selected:
                messagebox.showwarning(
                    "Warning", "Select a camera to add", parent=dialog
                )
                return

            item = results_tree.item(selected[0])
            values = item["values"]
            ip = values[0]
            rtsp_url = values[3] if len(values) > 3 else ""

            # Find the discovered camera
            cam_data = next((c for c in discovered if c.ip == ip), None)
            if not cam_data:
                return

            # Open dialog to get credentials
            self._add_discovered_camera_dialog(dialog, cam_data)

        # Buttons - pack at bottom FIRST so they always show
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        scan_btn = ttk.Button(btn_frame, text="Start Scan", command=start_scan)
        scan_btn.pack(side=tk.LEFT, padx=2)

        stop_btn = ttk.Button(btn_frame, text="Stop", command=stop_scan, state=tk.DISABLED)
        stop_btn.pack(side=tk.LEFT, padx=2)

        ttk.Button(btn_frame, text="Add Selected", command=add_selected).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(
            side=tk.RIGHT, padx=2
        )

        # Results - pack after buttons so it fills remaining space
        results_frame = ttk.LabelFrame(main_frame, text="Found Cameras", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        columns = ("ip", "ports", "manufacturer", "rtsp_url")
        results_tree = ttk.Treeview(
            results_frame, columns=columns, show="headings", height=6
        )
        results_tree.heading("ip", text="IP")
        results_tree.column("ip", width=120)
        results_tree.heading("ports", text="Ports")
        results_tree.column("ports", width=100)
        results_tree.heading("manufacturer", text="Type")
        results_tree.column("manufacturer", width=80)
        results_tree.heading("rtsp_url", text="Suggested RTSP URL")
        results_tree.column("rtsp_url", width=200)
        results_tree.pack(fill=tk.BOTH, expand=True)

    def _add_discovered_camera_dialog(
        self, parent: tk.Toplevel, cam_data: DiscoveredCamera
    ) -> None:
        """Dialog to add a discovered camera with credentials."""
        dialog = tk.Toplevel(parent)
        dialog.title(f"Add Camera - {cam_data.ip}")
        dialog.geometry("450x250")
        dialog.transient(parent)
        dialog.grab_set()
        center_window(dialog)

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # IP (readonly)
        ttk.Label(frame, text="IP:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ip_label = ttk.Label(frame, text=cam_data.ip)
        ip_label.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Manufacturer
        ttk.Label(frame, text="Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(frame, text=cam_data.manufacturer).grid(row=1, column=1, sticky=tk.W, pady=5)

        # Username
        ttk.Label(frame, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=5)
        user_entry = ttk.Entry(frame, width=30)
        user_entry.grid(row=2, column=1, pady=5, sticky=tk.W)
        user_entry.insert(0, "admin")

        # Password
        ttk.Label(frame, text="Password:").grid(row=3, column=0, sticky=tk.W, pady=5)
        pass_entry = ttk.Entry(frame, width=30, show="*")
        pass_entry.grid(row=3, column=1, pady=5, sticky=tk.W)

        # RTSP URL
        ttk.Label(frame, text="RTSP URL:").grid(row=4, column=0, sticky=tk.W, pady=5)
        rtsp_entry = ttk.Entry(frame, width=40)
        rtsp_entry.grid(row=4, column=1, pady=5, sticky=tk.W)

        # Generate initial RTSP URL
        suggested_url = cam_data.get_suggested_rtsp_url("admin", "")
        rtsp_entry.insert(0, suggested_url)

        def update_rtsp_url(*args) -> None:
            """Update RTSP URL with credentials."""
            user = user_entry.get().strip()
            passwd = pass_entry.get()
            url = cam_data.get_suggested_rtsp_url(user, passwd)
            rtsp_entry.delete(0, tk.END)
            rtsp_entry.insert(0, url)

        user_entry.bind("<FocusOut>", update_rtsp_url)
        pass_entry.bind("<FocusOut>", update_rtsp_url)

        def save_camera() -> None:
            """Save the camera configuration."""
            username = user_entry.get().strip()
            password = pass_entry.get()
            rtsp_url = rtsp_entry.get().strip()

            if not rtsp_url:
                messagebox.showerror("Error", "RTSP URL is required", parent=dialog)
                return

            # Determine port
            port = 554 if 554 in cam_data.ports else cam_data.ports[0] if cam_data.ports else 554

            camera = Camera(
                ip=cam_data.ip,
                port=port,
                username=username,
                password=password,
                rtsp_url=rtsp_url,
                logger_instance=self._logger,
            )

            if camera.connect():
                self.cameras.append(camera)
                self._populate_camera_list()
                save_cameras(self.cameras, self._logger)
                self._create_video_labels()
                dialog.destroy()
                self._logger.info(f"Camera added: {cam_data.ip}")
                messagebox.showinfo(
                    "Success",
                    f"Camera {cam_data.ip} added successfully!",
                    parent=parent,
                )
            else:
                messagebox.showerror(
                    "Error",
                    f"Failed to connect to {cam_data.ip}\n\nTry different credentials or RTSP URL.",
                    parent=dialog,
                )

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="Add Camera", command=save_camera).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(
            side=tk.RIGHT
        )

        user_entry.focus_set()

    # ==================== Window Controls ====================

    def _minimize(self) -> None:
        """Minimize the main window."""
        try:
            self.root.iconify()
            self._logger.info("Window minimized")
        except Exception as e:
            self._logger.error(f"Error minimizing: {e}")

    def _on_close(self) -> None:
        """Handle application close."""
        try:
            self._logger.info("Closing application...")
            self.running = False

            # Disconnect cameras
            self._logger.info("Disconnecting cameras...")
            for i, cam in enumerate(self.cameras):
                if isinstance(cam, Camera):
                    try:
                        cam.disconnect()
                    except Exception as e:
                        self._logger.error(f"Error disconnecting camera {i}: {e}")

            # Close camera manager
            if self._camera_list_window and self._camera_list_window.winfo_exists():
                try:
                    self._camera_list_window.destroy()
                except Exception:
                    pass

            # Destroy main window
            if self.root and self.root.winfo_exists():
                self.root.destroy()

            self._logger.info("Application closed")

        except Exception as e:
            self._logger.error(f"Critical error closing app: {e}", exc_info=True)
