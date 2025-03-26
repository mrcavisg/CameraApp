# Este código é o ponto de entrada do programa.

import tkinter as tk
import sys
import cv2
import onvif
from app import CameraApp
from utils import setup_logging

def main():
    logger = setup_logging()
    logger.info("Iniciando o programa principal...")

    # Configurar o caminho do FFmpeg
    if getattr(sys, 'frozen', False):
        ffmpeg_path = os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe")
        os.environ["OPENCV_FFMPEG_BINARY"] = ffmpeg_path
        logger.info(f"FFmpeg configurado para: {ffmpeg_path}")

    logger.info(f"Versão do Python: {sys.version}")
    logger.info(f"Versão do OpenCV: {cv2.__version__}")
    try:
        logger.info(f"Versão do ONVIF: {onvif.__version__}")
    except:
        logger.warning("Não foi possível obter a versão do ONVIF.")

    try:
        root = tk.Tk()
        logger.info("Tkinter inicializado com sucesso.")
        app = CameraApp(root, logger)
        root.mainloop()
    except Exception as e:
        logger.error(f"Erro fatal ao iniciar o programa: {e}")
        raise

if __name__ == "__main__":
    main()