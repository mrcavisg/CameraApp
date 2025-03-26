# Este código contém funções utilitárias, como configuração de logging e manipulação de arquivos JSON.

import logging
import json
import os
from datetime import datetime
from config import LOG_DIR, CAMERAS_JSON

def setup_logging():
    """Configura o logging para o aplicativo."""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    log_file = os.path.join(LOG_DIR, f"camera_app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    return logger

def save_cameras(cameras):
    """Salva a lista de câmeras em um arquivo JSON."""
    try:
        data = [{"ip": cam.ip, "port": cam.port, "username": cam.username,
                 "password": cam.password, "rtsp_url": cam.rtsp_url} for cam in cameras]
        with open(CAMERAS_JSON, "w") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao salvar configurações: {e}")
        return False

def load_cameras():
    """Carrega a lista de câmeras de um arquivo JSON."""
    try:
        with open(CAMERAS_JSON, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        logger = logging.getLogger(__name__)
        logger.warning(f"Arquivo {CAMERAS_JSON} não encontrado. Iniciando sem câmeras salvas.")
        return []
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao carregar configurações: {e}")
        return []