import logging
import logging.handlers
import os
import json
import sys  # Adicionada a importação de sys

def setup_logging(log_file):
    """
    Configura o logging para escrever em um arquivo e, opcionalmente, no console.
    
    Args:
        log_file (str): Caminho do arquivo de log.
    
    Returns:
        logging.Logger: Logger configurado.
    """
    # Criar um logger
    logger = logging.getLogger('utils')
    logger.setLevel(logging.INFO)

    # Evitar múltiplos handlers se a função for chamada mais de uma vez
    if not logger.handlers:
        # Criar um handler para o arquivo de log com rotação
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5*1024*1024, backupCount=5
        )
        file_handler.setLevel(logging.INFO)

        # Criar um handler para o console (opcional)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Definir o formato dos logs
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Adicionar os handlers ao logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

def save_cameras(cameras):
    """
    Salva a lista de câmeras em um arquivo JSON.
    """
    try:
        data_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "CFATech", "CameraApp")
        if getattr(sys, 'frozen', False):
            data_dir = os.path.join(os.path.dirname(sys.executable))
        os.makedirs(data_dir, exist_ok=True)
        config_file = os.path.join(data_dir, "cameras.json")
        
        camera_data = [
            {
                "ip": cam.ip,
                "port": cam.port,
                "username": cam.username,
                "password": cam.password,
                "rtsp_url": cam.rtsp_url
            }
            for cam in cameras
        ]
        
        with open(config_file, "w") as f:
            json.dump(camera_data, f, indent=4)
    except Exception as e:
        logger = logging.getLogger('utils')
        logger.error(f"Erro ao salvar câmeras: {e}")
        raise

def load_cameras():
    """
    Carrega a lista de câmeras de um arquivo JSON.
    """
    try:
        data_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "CFATech", "CameraApp")
        if getattr(sys, 'frozen', False):
            data_dir = os.path.join(os.path.dirname(sys.executable))
        config_file = os.path.join(data_dir, "cameras.json")
        
        if not os.path.exists(config_file):
            return []
        
        with open(config_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger = logging.getLogger('utils')
        logger.error(f"Erro ao carregar câmeras: {e}")
        raise