# config.py (CORRIGIDO v2 - Com constantes de Logging)
import os
import sys
import logging # Importa logging para usar seus níveis

# Importa appdirs ou usa um fallback
try:
    from appdirs import user_data_dir
except ImportError:
    # Função fallback simples
    def _fallback_user_data_dir(appname, appauthor):
        # No Linux/macOS, usa ~/.local/share/<appname> (mais padrão que pasta oculta)
        if sys.platform.startswith('linux') or sys.platform == 'darwin':
            path = os.path.join(os.path.expanduser("~"), ".local", "share", appname)
        # No Windows, usa %APPDATA%\<AppAuthor>\<AppName> (Appdirs faz isso melhor)
        elif sys.platform == 'win32':
            path = os.path.join(os.getenv('APPDATA', os.path.expanduser("~")), appauthor, appname)
        else: # Outros OS, usa pasta oculta no home
            path = os.path.join(os.path.expanduser("~"), "." + appname.lower() + "_data")
        return path
    user_data_dir = _fallback_user_data_dir # Usa o fallback
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
    except Exception: base_dir = os.path.expanduser("~") # Último recurso
    # Evita criar pasta oculta diretamente no diretório do script se falhar
    DATA_DIR = os.path.join(base_dir, "app_data")

LOG_DIR = os.path.join(DATA_DIR, "logs")
CAMERAS_JSON = os.path.join(DATA_DIR, "cameras.json")

# --- Configurações da Câmera (Exemplo) ---
# Você pode remover estas se não estiverem sendo usadas diretamente em outros módulos
# Ou mantenha-as para referência centralizada
CAMERA_CONNECT_TIMEOUT_ONVIF = 10
CAMERA_CONNECT_TIMEOUT_CV_OPEN = 10000
CAMERA_CONNECT_TIMEOUT_CV_READ = 15000
CAMERA_MAX_RETRIES = 5
CAMERA_RETRY_DELAY_BASE = 2
CAMERA_MAX_RETRY_WAIT = 60
CAMERA_FRAME_QUEUE_SIZE = 5
CAMERA_CONSECUTIVE_READ_FAILURES_LIMIT = 10

# --- Configurações da Interface ---
FRAME_UPDATE_INTERVAL = 30  # ms
DEFAULT_ASPECT_RATIO = "fit"

# --- Configurações de Logging (ADICIONADAS/GARANTIDAS) ---
LOG_LEVEL = logging.DEBUG # Use DEBUG para mais detalhes, INFO para produção
LOG_MAX_BYTES = 5 * 1024 * 1024 # 5MB
LOG_BACKUP_COUNT = 3 # Manter 3 backups

# --- Configurações de Rede (Exemplo) ---
ONVIF_DISCOVERY_TIMEOUT = 5
FORCE_TCP_TRANSPORT = True

# Logs Iniciais para depuração de caminhos (Opcional)
print(f"INFO [config]: Diretório de dados: {DATA_DIR}")
print(f"INFO [config]: Arquivo de câmeras: {CAMERAS_JSON}")
print(f"INFO [config]: Diretório de logs: {LOG_DIR}")
print(f"INFO [config]: Nível de log: {logging.getLevelName(LOG_LEVEL)}")