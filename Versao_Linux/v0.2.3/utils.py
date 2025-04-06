# utils.py (CORRIGIDO - v4 com import tk garantido)

import logging
import logging.handlers
import os
import json
import sys
import tkinter as tk # <<< GARANTA QUE ESTA LINHA ESTEJA AQUI NO TOPO

# IMPORTAR CONSTANTES DO CONFIG (com tratamento de erro e imports específicos)
try:
    # Importa APENAS o necessário
    from config import (DATA_DIR, CAMERAS_JSON, LOG_DIR,
                        LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOGGER_NAME)
except ImportError as e:
    print(f"ERRO CRÍTICO: Falha ao importar constantes de config.py: {e}. Usando fallbacks.", file=sys.stderr)
    # Define fallbacks essenciais se config.py falhar
    LOGGER_NAME = "CameraApp_Fallback"
    try: # Tenta determinar diretório base
        if getattr(sys, 'frozen', False): base_dir = os.path.dirname(sys.executable)
        else: base_dir = os.path.dirname(os.path.abspath(__file__))
    except Exception: base_dir = os.path.expanduser("~") # Último recurso
    DATA_DIR = os.path.join(base_dir, "." + LOGGER_NAME.lower() + "_data") # Pasta oculta
    LOG_DIR = os.path.join(DATA_DIR, "logs")
    CAMERAS_JSON = os.path.join(DATA_DIR, "cameras.json")
    LOG_LEVEL = logging.INFO
    LOG_MAX_BYTES = 1 * 1024 * 1024
    LOG_BACKUP_COUNT = 1
    print(f"AVISO: Usando paths de fallback para dados/logs: {DATA_DIR}", file=sys.stderr)

# Tenta importar Camera apenas para Type Hinting
try:
     from typing import List, TYPE_CHECKING
     if TYPE_CHECKING:
         from camera import Camera # Só para checagem de tipo
except ImportError:
     List = list # Fallback

# --- Configuração do Logging ---
def setup_logging():
    """Configura e retorna uma instância do logger para a aplicação."""
    logger = logging.getLogger(LOGGER_NAME)
    # Verifica se já foi configurado para evitar duplicação
    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)

    # Cria diretórios ANTES de configurar handlers
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file_path = os.path.join(LOG_DIR, "cameraapp.log") # Nome fixo
    except OSError as e:
        print(f"AVISO: Não foi possível criar diretório de logs '{LOG_DIR}': {e}", file=sys.stderr)
        log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cameraapp.log")

    formatter = logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)')

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(LOG_LEVEL)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler (Rotativo)
    try:
        fh = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        fh.setLevel(LOG_LEVEL)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        logger.info(f"Logging configurado. Arquivo: {log_file_path}")
    except PermissionError as e:
         logger.error(f"Sem permissão para escrever no arquivo de log: {log_file_path} - {e}")
         print(f"ERRO: Sem permissão para escrever no arquivo de log: {log_file_path}", file=sys.stderr)
    except Exception as e:
        logger.error(f"Falha ao configurar logging em arquivo: {e}", exc_info=True)
        print(f"ERRO: Falha ao configurar logging em arquivo: {e}", file=sys.stderr)

    return logger

# --- Funções para Salvar e Carregar Câmeras ---

def save_cameras(cameras: List['Camera'], logger: logging.Logger):
    """Salva as configurações das câmeras em um arquivo JSON."""
    log = logger
    filepath = CAMERAS_JSON
    try:
        camera_data = []
        for cam in cameras:
            if hasattr(cam, 'ip') and hasattr(cam, 'port') and hasattr(cam, 'username') \
               and hasattr(cam, 'password') and hasattr(cam, 'rtsp_url') and hasattr(cam, 'camera_type'):
                 camera_data.append({
                     "type": getattr(cam, 'camera_type', 'RTSP'),
                     "ip": cam.ip,
                     "port": cam.port,
                     "username": cam.username,
                     "password": cam.password, # ATENÇÃO: SENHA EM TEXTO PLANO!
                     "rtsp_url": cam.rtsp_url
                 })
            else: log.warning(f"Ignorando objeto inválido ao salvar câmeras: {type(cam)}")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(camera_data, f, indent=4)
        log.info(f"Configurações de {len(camera_data)} câmeras salvas em {filepath}")
        return True
    except PermissionError as e:
        log.error(f"Sem permissão para escrever no arquivo de config.: {filepath} - {e}")
        # messagebox só funciona se Tkinter estiver inicializado, evitamos aqui
        print(f"ERRO: Sem permissão para escrever no arquivo de config.: {filepath} - {e}", file=sys.stderr)
        return False
    except Exception as e:
        log.error(f"Erro ao salvar configurações das câmeras: {e}", exc_info=True)
        return False

def load_cameras(logger: logging.Logger) -> List['Camera']:
    """Carrega as configurações das câmeras do arquivo JSON."""
    log = logger
    cameras_list = []
    try: from camera import Camera # Importa AQUI dentro
    except ImportError as e:
        log.critical(f"Falha ao importar a classe Camera dentro de load_cameras: {e}. Verifique camera.py.")
        return []

    filepath = CAMERAS_JSON
    if not os.path.exists(filepath):
        log.warning(f"Arquivo config não encontrado: {filepath}. Nenhuma câmera carregada.")
        return cameras_list

    try:
        with open(filepath, "r", encoding='utf-8') as f:
            camera_data = json.load(f)
        log.debug(f"Dados carregados do JSON: {camera_data}")

        for data in camera_data:
            required_keys = ['ip', 'port', 'username', 'password']
            if all(k in data for k in required_keys):
                try:
                    cam = Camera(
                        ip=data['ip'],
                        port=int(data['port']),
                        username=data['username'],
                        password=data['password'],
                        rtsp_url=data.get('rtsp_url', ""),
                        camera_type=data.get('type', 'RTSP'),
                        logger_instance=log # Passa o logger
                    )
                    cameras_list.append(cam)
                except ValueError as e: log.error(f"Erro converter dados p/ IP {data.get('ip','??')}: {e}")
                except TypeError as e: log.error(f"Erro de Tipo ao criar Camera p/ IP {data.get('ip','??')}: {e}", exc_info=True)
                except Exception as e: log.error(f"Erro inesperado ao criar Camera p/ IP {data.get('ip','??')}: {e}", exc_info=True)
            else:
                missing_keys = [k for k in required_keys if k not in data]
                log.warning(f"Dados incompletos ignorados no JSON (faltam chaves: {missing_keys}): {data}")

        log.info(f"{len(cameras_list)} câmeras carregadas de {filepath}")
    except json.JSONDecodeError as e: log.error(f"Erro ao decodificar JSON {filepath}: {e}.")
    except Exception as e: log.error(f"Erro inesperado ao carregar câmeras: {e}", exc_info=True)

    return cameras_list

# --- Função Auxiliar para Centralizar Janelas ---
def center_window(window: tk.Misc): # tk.Misc funciona porque tk foi importado
    """Centraliza uma janela tk ou toplevel na tela."""
    log = logging.getLogger(LOGGER_NAME)
    try:
        if not window.winfo_exists(): return
        window.update_idletasks()
        width = window.winfo_width(); height = window.winfo_height()
        screen_width = window.winfo_screenwidth(); screen_height = window.winfo_screenheight()
        x = max(0, (screen_width // 2) - (width // 2)); y = max(0, (screen_height // 2) - (height // 2))
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.lift(); window.attributes('-topmost', True)
        window.after(100, lambda: window.attributes('-topmost', False))
        if window.winfo_exists() and window.state() == 'iconic': window.deiconify()
        window.focus_force()
    except tk.TclError as e:
         if "application has been destroyed" not in str(e): log.error(f"Erro Tcl ao centralizar janela '{getattr(window, 'title', '')()}': {e}")
    except Exception as e:
        log.error(f"Erro inesperado ao centralizar janela '{getattr(window, 'title', '')()}': {e}", exc_info=True)

# (Fim do arquivo utils.py)