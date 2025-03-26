import cv2
import threading
import logging
from onvif import ONVIFCamera

class Camera:
    def __init__(self, ip, port, username, password, rtsp_url="", logger=None):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.rtsp_url = rtsp_url
        self.logger = logger or logging.getLogger(__name__)
        self.connected = False
        self.cap = None
        self.thread = None
        self.stop_event = threading.Event()
        self.frame = None
        self.logger.info(f"Câmera criada: IP={self.ip}, Porta={self.port}, Usuário={self.username}, RTSP_URL={self.rtsp_url}")

    def connect(self):
        """
        Tenta conectar à câmera via ONVIF ou RTSP.
        Retorna True se a conexão for bem-sucedida, False caso contrário.
        """
        try:
            if self.rtsp_url:
                # Conexão via RTSP
                self.cap = cv2.VideoCapture(self.rtsp_url)
                if not self.cap.isOpened():
                    self.logger.error(f"Falha ao conectar à câmera RTSP: {self.rtsp_url}")
                    return False
            else:
                # Conexão via ONVIF
                onvif_cam = ONVIFCamera(self.ip, self.port, self.username, self.password)
                media_service = onvif_cam.create_media_service()
                profiles = media_service.GetProfiles()
                if not profiles:
                    self.logger.error(f"Nenhum perfil ONVIF encontrado para a câmera: {self.ip}")
                    return False
                stream_uri = media_service.GetStreamUri({'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': 'RTSP'}, 'ProfileToken': profiles[0].token})
                self.rtsp_url = stream_uri.Uri
                self.cap = cv2.VideoCapture(self.rtsp_url)
                if not self.cap.isOpened():
                    self.logger.error(f"Falha ao conectar à câmera ONVIF: {self.ip}, RTSP_URL={self.rtsp_url}")
                    return False

            self.connected = True
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            self.logger.info(f"Conexão bem-sucedida com a câmera: {self.ip}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao conectar à câmera {self.ip}: {e}")
            self.connected = False
            return False

    def _capture_frames(self):
        """
        Captura frames da câmera em um loop contínuo.
        """
        while not self.stop_event.is_set():
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    self.frame = frame
                else:
                    self.logger.warning(f"Falha ao capturar frame da câmera: {self.ip}")
                    self.connected = False
                    break
            else:
                self.logger.error(f"Conexão com a câmera perdida: {self.ip}")
                self.connected = False
                break

    def get_frame(self):
        """
        Retorna o último frame capturado.
        """
        if not self.connected or self.frame is None:
            return None
        return self.frame

    def disconnect(self):
        """
        Desconecta a câmera e libera os recursos.
        """
        self.logger.info(f"Desconectando câmera {self.ip}...")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        if self.cap:
            self.cap.release()
        self.connected = False
        self.logger.info(f"Câmera {self.ip} desconectada.")