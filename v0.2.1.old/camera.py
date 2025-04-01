# camera.py
import cv2
# from onvif import ONVIFCamera # Movido para dentro do connect para evitar importação se não for usar ONVIF? Ou manter global? Manter global é mais simples.
from onvif import ONVIFCamera
import logging
import os
# get_onvif_wsdl_files não é mais necessário aqui se onvif-zeep gerencia o WSDL
# from wsdl_utils import get_onvif_wsdl_files
from zeep.transports import Transport
import requests

class Camera:
    def __init__(self, ip, port, username, password, rtsp_url="", logger=None):
        self.ip = ip
        self.port = int(port) # Garantir que a porta seja int
        self.username = username
        self.password = password
        self.rtsp_url = rtsp_url
        # Usar o logger passado ou obter um logger com nome específico se nenhum for fornecido
        # O ideal é que o logger seja sempre passado por quem cria a Camera
        self.logger = logger or logging.getLogger(f"{__name__}.{ip}") # Logger específico da instância
        self.logger.debug(f"Inicializando objeto Camera: IP={ip}, Porta={self.port}, Usuário={username}, RTSP_URL={rtsp_url}")
        self.onvif_cam = None
        self.cap = None
        self.connected = False
        self.media_service = None # Adicionado para reutilizar o serviço
        self.token = None # Adicionado para guardar o token do perfil

    def connect(self, timeout=10):
        """Tenta conectar à câmera via RTSP direto ou ONVIF."""
        self.logger.info(f"Tentando conectar a {self.ip}:{self.port}...")
        self.disconnect() # Garantir que qualquer conexão anterior seja fechada

        try:
            effective_rtsp_url = self.rtsp_url # Começa com o URL fornecido, se houver

            # Se não houver URL RTSP explícito, tentar ONVIF
            if not effective_rtsp_url:
                self.logger.info(f"URL RTSP não fornecido para {self.ip}. Tentando descoberta ONVIF...")
                # WSDL_DIR agora é gerenciado internamente por onvif-zeep geralmente
                # wsdl_dir = os.path.join(os.path.dirname(__file__), 'wsdl') # Caminho relativo
                # self.logger.debug(f"Usando diretório WSDL: {wsdl_dir}")
                # os.makedirs(wsdl_dir, exist_ok=True) # Garante que exista

                # Configurar transporte com timeout
                transport = Transport(timeout=timeout)
                try:
                    self.onvif_cam = ONVIFCamera(
                        self.ip,
                        self.port,
                        self.username,
                        self.password,
                        # wsdl_dir, # onvif-zeep geralmente encontra automaticamente
                        transport=transport,
                        no_cache=True # Adicionado para evitar cache zeep persistente que pode dar problema
                    )
                    self.logger.info(f"Autenticação ONVIF com {self.ip} iniciada.")

                    # Criar serviço de mídia (necessário para obter perfis e URI)
                    self.media_service = self.onvif_cam.create_media_service()
                    self.logger.debug(f"Serviço de Mídia ONVIF criado para {self.ip}.")

                    # Obter perfis de mídia
                    profiles = self.media_service.GetProfiles()
                    self.logger.debug(f"{len(profiles)} perfil(es) ONVIF encontrado(s) para {self.ip}.")

                    if profiles:
                        # **Ponto de melhoria futuro: Seleção de Perfil**
                        # Por enquanto, pega o primeiro perfil.
                        # Idealmente, deveríamos permitir ao usuário escolher ou ter uma lógica melhor.
                        selected_profile = profiles[0]
                        self.token = selected_profile.token # Guardar o token do perfil usado
                        self.logger.info(f"Usando perfil ONVIF: {selected_profile.Name} (token: {self.token})")

                        # Obter o URI do stream RTSP para o perfil selecionado
                        req = self.media_service.create_type('GetStreamUri')
                        req.ProfileToken = self.token
                        req.StreamSetup = {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}} # Ou 'TCP' ? Testar. Tentar UDP primeiro (RTSP)
                        self.logger.debug(f"Requisitando Stream URI para perfil {self.token}")
                        stream_uri_info = self.media_service.GetStreamUri(req)

                        effective_rtsp_url = stream_uri_info.Uri
                        self.logger.info(f"URL RTSP obtido via ONVIF para {self.ip}: {effective_rtsp_url}")
                        # Atualizar o rtsp_url da instância caso ele não tenha sido fornecido
                        if not self.rtsp_url:
                             self.rtsp_url = effective_rtsp_url

                    else:
                        self.logger.error(f"Nenhum perfil de mídia encontrado para a câmera ONVIF: {self.ip}")
                        return False

                except Exception as onvif_error:
                    self.logger.error(f"Falha na comunicação ONVIF com {self.ip}:{self.port}: {onvif_error}", exc_info=True)
                    self.onvif_cam = None # Limpar em caso de erro
                    self.media_service = None
                    return False

            # Se temos um URL RTSP (fornecido ou via ONVIF), tentar conectar com OpenCV
            if effective_rtsp_url:
                 self.logger.info(f"Tentando abrir stream RTSP: {effective_rtsp_url}")
                 # Definir variáveis de ambiente pode ajudar com latência/timeout em alguns casos
                 # os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp" # Forçar TCP
                 # os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "stimeout;5000000" # Timeout 5s (em microssegundos)

                 self.cap = cv2.VideoCapture(effective_rtsp_url, cv2.CAP_FFMPEG) # Tentar especificar backend FFMPEG

                 if self.cap.isOpened():
                     self.connected = True
                     # Ler algumas propriedades do vídeo se possível
                     width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                     height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                     fps = self.cap.get(cv2.CAP_PROP_FPS)
                     self.logger.info(f"Conexão RTSP bem-sucedida com {self.ip} via {effective_rtsp_url} [{int(width)}x{int(height)} @ {fps:.2f} FPS]")
                     return True
                 else:
                     self.logger.error(f"Falha ao abrir stream RTSP: {effective_rtsp_url}")
                     self.cap = None # Limpar cap se falhou
                     return False
            else:
                 # Caso onde não tínhamos URL e ONVIF falhou em obter um
                 self.logger.error(f"Não foi possível obter um URL RTSP para {self.ip} via ONVIF.")
                 return False

        except Exception as e:
            self.logger.error(f"Erro inesperado ao conectar à câmera {self.ip}: {e}", exc_info=True)
            self.disconnect() # Garante limpeza em caso de erro
            return False

    # ... (get_frame e disconnect permanecem iguais, mas usarão self.logger que agora é mais específico) ...

    def get_frame(self):
        """Lê um frame do stream de vídeo se conectado."""
        if not self.connected or not self.cap:
            # self.logger.debug(f"Tentativa de obter frame de câmera não conectada: {self.ip}") # Log muito verboso
            return None
        try:
            # Definir um timeout na leitura pode ser útil, mas VideoCapture não suporta nativamente.
            # Se get_frame bloquear, precisará de threading.
            ret, frame = self.cap.read()
            if ret:
                return frame
            else:
                self.logger.warning(f"Falha ao ler frame (ret=False) da câmera: {self.ip}. Desconectando.")
                self.disconnect() # Desconectar se a leitura falhar
                return None
        except Exception as e:
            self.logger.error(f"Erro durante cap.read() da câmera {self.ip}: {e}", exc_info=True)
            self.disconnect() # Desconectar em caso de exceção
            return None

    def disconnect(self):
        """Libera os recursos da câmera."""
        if self.cap:
            self.logger.info(f"Liberando captura de vídeo para {self.ip}...")
            try:
                 self.cap.release()
                 self.logger.info(f"Captura de vídeo para {self.ip} liberada.")
            except Exception as e:
                 self.logger.error(f"Erro ao liberar self.cap para {self.ip}: {e}", exc_info=True)
            self.cap = None
        # Não precisamos desconectar explicitamente onvif_cam, a conexão é refeita a cada tentativa se necessário.
        # self.onvif_cam = None # Resetar se quiser forçar recriação
        # self.media_service = None
        # self.token = None
        if self.connected:
             self.connected = False
             self.logger.info(f"Câmera marcada como desconectada: {self.ip}")