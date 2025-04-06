# config.py (CORRIGIDO - Com constantes de Logging)
import os
import sys
import logging # Importa logging para usar seus níveis

# Importa appdirs ou usa um fallback
try:
    from appdirs import user_data_dir
except ImportError:
    user_data_dir = lambda appname, appauthor: os.path.join(os.path.expanduser("~"), "." + appname.lower() + "_data")
    print("AVISO: Biblioteca 'appdirs' não encontrada. Usando diretório de dados fallback.", file=sys.stderr)

# --- Configurações do Aplicativo ---
APP_NAME = "CameraApp"
APP_AUTHOR = "CFATech"
LOGGER_NAME = APP_NAME # Define o nome do logger global aqui

# --- Diretórios (Usando appdirs ou fallback) ---
try:
    DATA_DIR = user_data_dir(APP_NAME, APP_AUTHOR)
except Exception as e:
    print(f"AVISO: Erro ao usar user_data_dir: {e}. Usando diretório atual como fallback.", file=sys.stderr)
    try: # Tenta determinar diretório base
        if getattr(sys, 'frozen', False): base_dir = os.path.dirname(sys.executable)
        else: base_dir = os.path.dirname(os.path.abspath(__file__))
    except Exception: base_dir = os.path.expanduser("~")
    DATA_DIR = os.path.join(base_dir, "." + APP_NAME.lower() + "_data")

LOG_DIR = os.path.join(DATA_DIR, "logs")
CAMERAS_JSON = os.path.join(DATA_DIR, "cameras.json")

# --- Configurações da Câmera ---
CAMERA_CONNECT_TIMEOUT_ONVIF = 10 # Timeout para conexão ONVIF (segundos)
CAMERA_CONNECT_TIMEOUT_CV_OPEN = 10000 # Timeout ABERTURA OpenCV (ms)
CAMERA_CONNECT_TIMEOUT_CV_READ = 15000 # Timeout LEITURA OpenCV (ms)
CAMERA_MAX_RETRIES = 5 # Máximo de tentativas de reconexão
CAMERA_RETRY_DELAY_BASE = 2 # Base para espera exponencial (segundos)
CAMERA_MAX_RETRY_WAIT = 60 # Tempo máximo de espera entre tentativas (segundos)
CAMERA_FRAME_QUEUE_SIZE = 5 # Tamanho da fila de frames
CAMERA_CONSECUTIVE_READ_FAILURES_LIMIT = 10 # Limite de falhas de leitura seguidas

# --- Configurações da Interface ---
FRAME_UPDATE_INTERVAL = 30  # Intervalo de atualização dos frames (ms) ~33 FPS
DEFAULT_ASPECT_RATIO = "fit" # 'fit', '4:3', '16:9'

# --- Configurações de Logging (ADICIONADAS/CORRIGIDAS) ---
LOG_LEVEL = logging.DEBUG # Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_MAX_BYTES = 5 * 1024 * 1024 # Tamanho máximo do arquivo de log (5MB)
LOG_BACKUP_COUNT = 3 # Quantos arquivos de backup manter

# --- Configurações de Rede ---
ONVIF_DISCOVERY_TIMEOUT = 5 # Timeout para busca ONVIF (segundos)
FORCE_TCP_TRANSPORT = True # Forçar TCP para RTSP no OpenCV

# Logs Iniciais (Opcional, mas útil para depurar caminhos)
print(f"INFO [config]: Diretório de dados: {DATA_DIR}")
print(f"INFO [config]: Arquivo de câmeras: {CAMERAS_JSON}")
print(f"INFO [config]: Diretório de logs: {LOG_DIR}")