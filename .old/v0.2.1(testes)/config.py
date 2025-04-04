import os
from appdirs import user_data_dir

# Este código configurações globais e constantes.

# Configurações do aplicativo
APP_NAME = "CameraApp"
APP_AUTHOR = "CFATech"

# Diretórios
DATA_DIR = user_data_dir(APP_NAME, APP_AUTHOR)
LOG_DIR = os.path.join(DATA_DIR, "logs")
CAMERAS_JSON = os.path.join(DATA_DIR, "cameras.json")

# Configurações de câmera
MAX_FRAME_QUEUE_SIZE = 10
MAX_RETRIES = 5
RETRY_DELAY_BASE = 2  # Base para o backoff exponencial (em segundos)
FRAME_UPDATE_INTERVAL = 30  # Intervalo de atualização de frames (em milissegundos)

# Intervalo de atualização dos frames em milissegundos
FRAME_UPDATE_INTERVAL = 30

