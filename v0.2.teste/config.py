# config.py
import os
from appdirs import user_data_dir

APP_NAME = "CameraApp"
APP_AUTHOR = "CFATech"

DATA_DIR = user_data_dir(APP_NAME, APP_AUTHOR)
LOG_DIR = os.path.join(DATA_DIR, "logs")
CAMERAS_JSON = os.path.join(DATA_DIR, "cameras.json")

MAX_FRAME_QUEUE_SIZE = 10
MAX_RETRIES = 5
RETRY_DELAY_BASE = 2
FRAME_UPDATE_INTERVAL = 30