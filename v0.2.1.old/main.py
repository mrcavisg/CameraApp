# main.py
import tkinter as tk
import logging
import os
import sys
from app import CameraApp
from utils import setup_logging # setup_logging agora configura o root logger
# Importar de config
from config import LOG_DIR, APP_NAME

def main():
    # Construir o caminho do arquivo de log usando LOG_DIR e APP_NAME
    # Não precisa mais verificar 'frozen', appdirs cuida disso
    os.makedirs(LOG_DIR, exist_ok=True) # Garante que o diretório exista
    log_file = os.path.join(LOG_DIR, f"{APP_NAME.lower()}.log")

    # Configurar o logging globalmente (root logger)
    setup_logging(log_file)

    # Obter um logger para o módulo main
    logger = logging.getLogger(__name__) # Ou logging.getLogger(APP_NAME)

    logger.info(f"*****************************************")
    logger.info(f"Iniciando {APP_NAME}")
    logger.info(f"Diretório de Dados: {os.path.dirname(log_file)}") # LOG_DIR é o diretório
    logger.info(f"Arquivo de Log: {log_file}")
    logger.info(f"Versão Python: {sys.version}")
    logger.info(f"Plataforma: {sys.platform}")
    logger.info(f"*****************************************")


    try:
        root = tk.Tk()
        # Passar o logger obtido para a CameraApp
        app = CameraApp(root, logger)
        root.mainloop()
        logger.info(f"{APP_NAME} finalizado normalmente.")
    except Exception as e:
        logger.critical(f"Erro fatal ao executar o aplicativo: {e}", exc_info=True) # Usar critical para erros fatais
        # raise # Talvez não relançar para evitar fechar a janela de console imediatamente
        sys.exit(1) # Sair com código de erro

if __name__ == "__main__":
    main()