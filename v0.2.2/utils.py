# utils.py

import logging
import logging.handlers
import os
import json
import sys
# IMPORTAR DO CONFIG
try:
    from config import DATA_DIR, CAMERAS_JSON, LOG_DIR, APP_NAME
    logger_name = APP_NAME
except (ImportError, NameError):
    # Definições de fallback se config.py não for encontrado ou não tiver as consts
    APP_NAME = "CameraApp_Fallback"
    logger_name = APP_NAME
    if getattr(sys, 'frozen', False):
        BASE_DIR = os.path.dirname(sys.executable)
        DATA_DIR = os.path.join(BASE_DIR)
        LOG_DIR = os.path.join(BASE_DIR, "logs")
    else:
        DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", APP_NAME)
        LOG_DIR = os.path.join(DATA_DIR, "logs")
    CAMERAS_JSON = os.path.join(DATA_DIR, "cameras.json")
    print(f"AVISO: Usando paths de fallback para dados/logs: {DATA_DIR}", file=sys.stderr)

def setup_logging(log_file=None):
    """Configura e retorna uma instância do logger para a aplicação."""
    # Usa o logger_name definido acima
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    if not log_file:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            log_file = os.path.join(LOG_DIR, f"{logger_name.lower()}.log")
        except OSError as e:
            print(f"ERRO: Criar diretório de log {LOG_DIR} falhou: {e}", file=sys.stderr)
            log_file = f"{logger_name.lower()}_fallback.log"

    if not logger.handlers:
        try:
            # File Handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            # Console Handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO) # Info para console
            # Formatter
            log_format = '%(asctime)s - %(name)s [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)'
            formatter = logging.Formatter(log_format)
            file_handler.setFormatter(formatter); console_handler.setFormatter(formatter)
            # Add handlers
            logger.addHandler(file_handler); logger.addHandler(console_handler)
            logger.info(f"Logging configurado. Arquivo: {log_file}")
        except Exception as e:
             print(f"ERRO CRÍTICO config handlers logging: {e}", file=sys.stderr)
    else: logger.debug("Handlers de logging já existem.")
    return logger

# --- Funções save_cameras e load_cameras ---

def save_cameras(cameras, logger=None): # Aceita logger
    """Salva a lista de objetos Camera no arquivo JSON."""
    log = logger or logging.getLogger(logger_name) # Usa logger passado ou global
    from camera import Camera # Importa localmente
    try:
        os.makedirs(DATA_DIR, exist_ok=True) # Usa DATA_DIR
        config_file = CAMERAS_JSON # Usa CAMERAS_JSON

        camera_data = []
        for cam in cameras:
            if isinstance(cam, Camera):
                 camera_data.append({
                     "ip": cam.ip, "port": cam.port,
                     "username": cam.username, "password": cam.password, # Atenção: Senha em texto plano!
                     "rtsp_url": cam.rtsp_url
                 })
            else: log.warning(f"Item inválido ignorado ao salvar: {type(cam)}")

        with open(config_file, "w", encoding='utf-8') as f:
            json.dump(camera_data, f, indent=4)
        log.info(f"Configuração de {len(camera_data)} câmeras salva em {config_file}")
    except Exception as e:
        log.error(f"Erro ao salvar câmeras em {config_file}: {e}", exc_info=True)
        # Não relançar erro aqui, apenas logar.

def load_cameras(logger=None): # Aceita logger
    """Carrega a configuração das câmeras do arquivo JSON."""
    log = logger or logging.getLogger(logger_name)
    config_file = CAMERAS_JSON
    cameras_list = []
    from camera import Camera # Importa localmente

    if not os.path.exists(config_file):
        log.warning(f"Arquivo config não encontrado: {config_file}.")
        return cameras_list

    try:
        with open(config_file, "r", encoding='utf-8') as f:
            camera_data = json.load(f)
        log.debug(f"Dados carregados do JSON: {camera_data}") # Log para depuração

        for data in camera_data:
            if all(k in data for k in ('ip', 'port', 'username', 'password')):
                try:
                    cam = Camera(
                        ip=data['ip'], port=int(data['port']),
                        username=data['username'], password=data['password'],
                        rtsp_url=data.get('rtsp_url', ""),
                        logger=log # Passa o logger correto
                    )
                    cameras_list.append(cam)
                except ValueError as e: log.error(f"Erro converter dados p/ IP {data.get('ip','??')}: {e}")
                except Exception as e: log.error(f"Erro criar Camera p/ IP {data.get('ip','??')}: {e}", exc_info=True)
            else: log.warning(f"Dados incompletos ignorados no JSON: {data}")

        log.info(f"{len(cameras_list)} câmeras carregadas de {config_file}")
    except json.JSONDecodeError as e: log.error(f"Erro decodificar JSON {config_file}: {e}.")
    except Exception as e: log.error(f"Erro carregar câmeras de {config_file}: {e}", exc_info=True)

    return cameras_list