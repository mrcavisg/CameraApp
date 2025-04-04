# utils.py

import logging
import logging.handlers
import os
import json
import sys
# IMPORTAR DO CONFIG
try:
    # Usar APP_NAME também para o nome do logger é uma boa prática
    from config import DATA_DIR, CAMERAS_JSON, LOG_DIR, APP_NAME
except ImportError:
    # Definições de fallback se config.py não for encontrado
    APP_NAME = "CameraApp" # Defina um nome padrão
    # Defina fallbacks para os diretórios se necessário
    if getattr(sys, 'frozen', False):
        BASE_DIR = os.path.dirname(sys.executable)
        DATA_DIR = os.path.join(BASE_DIR)
        LOG_DIR = os.path.join(BASE_DIR, "logs")
    else:
        # Use a estrutura desejada para fallback, ex: ~/.local/share/YourApp
        # Ajuste o path se necessário. Usando APP_NAME aqui também.
        DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", APP_NAME)
        LOG_DIR = os.path.join(DATA_DIR, "logs")
    CAMERAS_JSON = os.path.join(DATA_DIR, "cameras.json")


def setup_logging(log_file=None):
    """Configura e retorna uma instância do logger para a aplicação."""
    logger_name = APP_NAME if 'APP_NAME' in globals() else 'utils_fallback'

    # Define o caminho do arquivo de log usando LOG_DIR se não for fornecido
    if not log_file:
        try:
            os.makedirs(LOG_DIR, exist_ok=True) # Garante que o diretório de log exista
            # Usa o nome do APP_NAME para o arquivo de log (ex: cameraapp.log)
            log_file = os.path.join(LOG_DIR, f"{logger_name.lower()}.log")
        except OSError as e:
            print(f"ERRO: Não foi possível criar o diretório de log {LOG_DIR}: {e}", file=sys.stderr)
            log_file = f"{logger_name.lower()}_fallback.log" # Fallback no diretório atual

    # Obtém a instância do logger usando o nome da aplicação
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG) # Define o nível de log geral

    # Adiciona handlers apenas se o logger ainda não tiver sido configurado
    if not logger.handlers:
        try:
            # Handler para arquivo (com rotação)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG) # Nível do handler de arquivo

            # Handler para console
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO) # Nível do console (INFO ou DEBUG)

            # Formatter (formato da mensagem de log)
            log_format = '%(asctime)s - %(name)s [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)'
            formatter = logging.Formatter(log_format)

            # Define o formatter para os handlers
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            # Adiciona os handlers ao logger
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

            logger.info(f"Logging configurado. Saída no console e no arquivo: {log_file}")

        except Exception as e:
             print(f"ERRO CRÍTICO ao configurar handlers de logging: {e}", file=sys.stderr)
    else:
        logger.debug("Logger já possuía handlers. Não foram adicionados novos handlers.")

    # Retorna a instância do logger configurada
    return logger

# --- Funções save_cameras e load_cameras ---

# !! IMPORTANTE: load_cameras e save_cameras ACEITAM logger=None !!
def save_cameras(cameras, logger=None):
    """Salva a lista de objetos Camera no arquivo JSON."""
    logger_name = APP_NAME if 'APP_NAME' in globals() else 'utils_fallback'
    log = logger or logging.getLogger(logger_name) # Obtém o logger
    # Importar Camera aqui evita import circular se Camera importar utils
    from camera import Camera
    try:
        os.makedirs(DATA_DIR, exist_ok=True) # Usa DATA_DIR de config
        config_file = CAMERAS_JSON # Usa CAMERAS_JSON de config

        camera_data = []
        for cam in cameras:
            if isinstance(cam, Camera):
                 camera_data.append({
                     "ip": cam.ip, "port": cam.port,
                     "username": cam.username, "password": cam.password,
                     "rtsp_url": cam.rtsp_url
                 })
            else:
                 log.warning(f"Item inválido na lista de câmeras ignorado ao salvar: {type(cam)}")

        with open(config_file, "w", encoding='utf-8') as f:
            json.dump(camera_data, f, indent=4)
        log.info(f"Configuração de {len(camera_data)} câmeras salva em {config_file}")

    except OSError as e:
         log.error(f"Erro de OS ao tentar criar diretório ou salvar câmeras em {CAMERAS_JSON}: {e}", exc_info=True)
    except TypeError as e:
         log.error(f"Erro de tipo ao preparar dados da câmera para JSON: {e}", exc_info=True)
    except Exception as e:
        log.error(f"Erro inesperado ao salvar câmeras em {CAMERAS_JSON}: {e}", exc_info=True)

# !! IMPORTANTE: load_cameras ACEITA logger=None !!
# Dentro de utils.py - Substitua a função load_cameras por esta:

# !! IMPORTANTE: load_cameras ACEITA logger=None !!
def load_cameras(logger=None):
    """Carrega a configuração das câmeras do arquivo JSON."""
    # Determina o nome do logger a ser usado
    logger_name = APP_NAME if 'APP_NAME' in globals() else 'utils_fallback'
    # Usa o logger passado como argumento ou pega um novo logger
    log = logger or logging.getLogger(logger_name)
    # Obtém o caminho do arquivo JSON de config.py (ou fallback)
    config_file = CAMERAS_JSON if 'CAMERAS_JSON' in globals() else "cameras_fallback.json"
    cameras_list = [] # Nome da lista local
    from camera import Camera # Importa a classe Camera

    if not os.path.exists(config_file):
        log.warning(f"Arquivo de configuração não encontrado: {config_file}. Nenhuma câmera será carregada.")
        return cameras_list # Retorna lista vazia

    try:
        with open(config_file, "r", encoding='utf-8') as f:
            camera_data = json.load(f)

        for data in camera_data:
            # Verifica se os campos essenciais existem no dicionário 'data'
            if all(k in data for k in ('ip', 'port', 'username', 'password')):
                try:
                    # Cria a instância da Câmera passando o logger
                    cam = Camera(
                        ip=data['ip'],
                        port=int(data['port']), # Garante que porta seja int
                        username=data['username'],
                        password=data['password'],
                        rtsp_url=data.get('rtsp_url', ""), # Usa get para evitar erro se 'rtsp_url' não existir
                        logger=log # Passa o logger correto
                    )
                    cameras_list.append(cam)
                except ValueError as e:
                     log.error(f"Erro ao converter dados da câmera (porta inválida?) para IP {data.get('ip', '??')}: {e}")
                except Exception as e:
                     log.error(f"Erro ao criar objeto Camera para IP {data.get('ip', '??')}: {e}", exc_info=True)
            else:
                log.warning(f"Dados de câmera incompletos ignorados no JSON: {data}")

        log.info(f"{len(cameras_list)} câmeras carregadas de {config_file}")

    except json.JSONDecodeError as e:
        log.error(f"Erro ao decodificar o arquivo JSON de câmeras ({config_file}): {e}. Verifique o formato.")
    except FileNotFoundError:
         log.error(f"Erro interno: Arquivo {config_file} não encontrado após verificação.")
    except Exception as e:
        log.error(f"Erro inesperado ao carregar câmeras de {config_file}: {e}", exc_info=True)

    return cameras_list # Retorna a lista de objetos Camera