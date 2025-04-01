# utils.py
import logging
import logging.handlers
import os
import json
import sys
# Importar as constantes de config
from config import DATA_DIR, CAMERAS_JSON, APP_NAME

# Modificar setup_logging para configurar o logger root
# e aceitar o caminho completo do arquivo de log
def setup_logging(log_file):
    """Configura o logging root para arquivo e console."""
    # Obter o logger root
    logger = logging.getLogger()
    # Definir o nível mais baixo (DEBUG) no logger root para capturar tudo
    logger.setLevel(logging.DEBUG)

    # Evitar adicionar múltiplos handlers se a função for chamada mais de uma vez
    # Limpar handlers existentes pode ser mais seguro em alguns cenários
    if logger.hasHandlers():
        logger.handlers.clear()

    # Handler para arquivo rotativo
    os.makedirs(os.path.dirname(log_file), exist_ok=True) # Garante que o diretório de log exista
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8' # Adicionado encoding
    )
    file_handler.setLevel(logging.DEBUG) # Nível para o arquivo

    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout) # Usar sys.stdout explicitamente
    console_handler.setLevel(logging.INFO) # Nível para o console (pode ser INFO ou DEBUG)

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Adicionar handlers ao logger root
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Retornar o logger configurado (opcional, pois a configuração é global agora)
    # return logger # Não precisa retornar, a configuração é no root logger

# Obter um logger específico para este módulo
module_logger = logging.getLogger(__name__)

def save_cameras(cameras):
    """Salva a lista de objetos Camera no arquivo JSON definido em config."""
    try:
        # Usar DATA_DIR de config.py
        os.makedirs(DATA_DIR, exist_ok=True)
        # Usar CAMERAS_JSON de config.py
        config_file = CAMERAS_JSON

        camera_data = []
        for i, cam in enumerate(cameras):
             # Adicionado verificação de tipo para robustez
            if not isinstance(cam, object) or not hasattr(cam, 'ip'):
                 module_logger.error(f"Item na lista de câmeras (índice {i}) não é um objeto Camera válido: {cam}")
                 continue
            camera_data.append({
                "ip": cam.ip,
                "port": cam.port,
                "username": cam.username,
                "password": cam.password, # Atenção: Senha em texto plano
                "rtsp_url": cam.rtsp_url
            })

        with open(config_file, "w", encoding='utf-8') as f: # Adicionado encoding
            json.dump(camera_data, f, indent=4)
        module_logger.info(f"Configuração das câmeras salva em {config_file}")

    except Exception as e:
        # Usar o logger específico do módulo
        module_logger.error(f"Erro ao salvar câmeras em {CAMERAS_JSON}: {e}", exc_info=True)
        # Não relançar a exceção aqui pode ser mais seguro para não parar a app
        # raise # Comentado para evitar parar a aplicação por falha ao salvar

def load_cameras():
    """Carrega a lista de câmeras do arquivo JSON definido em config."""
    # Importar Camera aqui para evitar importação circular se Camera usar utils
    from camera import Camera
    cameras = []
    # Usar CAMERAS_JSON de config.py
    config_file = CAMERAS_JSON

    if not os.path.exists(config_file):
        module_logger.warning(f"Arquivo de configuração de câmeras não encontrado: {config_file}. Nenhuma câmera carregada.")
        return cameras # Retorna lista vazia se o arquivo não existe

    try:
        with open(config_file, "r", encoding='utf-8') as f: # Adicionado encoding
            camera_data = json.load(f)

        for data in camera_data:
            # Garantir que todos os campos necessários estão presentes
            if all(k in data for k in ("ip", "port", "username", "password")):
                 # Passar o logger ao criar a instância de Camera
                 # Usar um nome de logger específico para cada câmera
                 cam_logger = logging.getLogger(f"Camera.{data['ip']}")
                 cameras.append(Camera(
                     ip=data["ip"],
                     port=data["port"],
                     username=data["username"],
                     password=data["password"],
                     rtsp_url=data.get("rtsp_url", ""), # Usar get para caso rtsp_url não exista
                     logger=cam_logger # Passando o logger criado
                 ))
            else:
                 module_logger.warning(f"Dados de câmera incompletos ignorados no arquivo {config_file}: {data}")
        module_logger.info(f"{len(cameras)} câmeras carregadas de {config_file}")

    except json.JSONDecodeError as e:
        module_logger.error(f"Erro ao decodificar JSON do arquivo {config_file}: {e}. O arquivo pode estar corrompido.")
    except Exception as e:
        module_logger.error(f"Erro ao carregar câmeras de {config_file}: {e}", exc_info=True)

    return cameras