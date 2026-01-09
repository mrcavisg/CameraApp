"""
Main entry point for CameraApp.

This module initializes logging, creates the main window,
and starts the application.
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import messagebox


def main() -> int:
    """
    Main entry point for the application.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    # Set main thread name
    threading.current_thread().name = "MainThread"

    # Import and setup logging
    try:
        from cameraapp.utils import setup_logging

        logger = setup_logging()
    except ImportError as e:
        print(f"CRITICAL: Failed to import utils: {e}", file=sys.stderr)
        return 1

    # Import CameraApp
    try:
        from cameraapp.app import CameraApp
    except ImportError as import_err:
        logger.critical(f"Failed to import CameraApp: {import_err}", exc_info=True)
        try:
            root_err = tk.Tk()
            root_err.withdraw()
            messagebox.showerror(
                "Import Error",
                f"Could not load application.\nError: {import_err}",
            )
            root_err.destroy()
        except Exception:
            pass
        return 1
    except Exception as general_err:
        logger.critical(
            f"Unexpected error importing CameraApp: {general_err}",
            exc_info=True,
        )
        try:
            root_err = tk.Tk()
            root_err.withdraw()
            messagebox.showerror(
                "Critical Error",
                f"Error loading application.\nError: {general_err}",
            )
            root_err.destroy()
        except Exception:
            pass
        return 1

    # Run application
    logger.info("=" * 20 + " Application Started " + "=" * 20)
    root = None
    exit_code = 0

    try:
        root = tk.Tk()
        app = CameraApp(root, logger)
        root.mainloop()

    except Exception as e:
        logger.critical(f"Unhandled exception in main application: {e}", exc_info=True)
        exit_code = 1
        try:
            if root and root.winfo_exists():
                messagebox.showerror(
                    "Critical Error",
                    f"Fatal error:\n{e}\n\nCheck logs for details.",
                )
        except Exception:
            pass

    finally:
        logger.info("=" * 20 + " Application Finished " + "=" * 20)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
