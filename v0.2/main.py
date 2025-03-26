import tkinter as tk
import logging
import os
import sys
from app import CameraApp
from utils import setup_logging

def main():
    # Configurar o logging
    log_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "CFATech", "CameraApp", "logs")
    if getattr(sys, 'frozen', False):
        # Se for um executável, ajustar o caminho do log
        log_dir = os.path.join(os.path.dirname(sys.executable), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "camera_app.log")
    
    logger = setup_logging(log_file)
    logger.info("Aplicativo iniciado.")

    try:
        root = tk.Tk()
        app = CameraApp(root, logger)
        root.mainloop()
    except Exception as e:
        logger.error(f"Erro ao iniciar o aplicativo: {e}")
        raise

if __name__ == "__main__":
    main()