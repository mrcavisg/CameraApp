# camera.py
import cv2
from onvif import ONVIFCamera
import logging
import os
from wsdl_utils import get_onvif_wsdl_files
from zeep.transports import Transport
import requests

class Camera:
    def __init__(self, ip, port, username, password, rtsp_url="", logger=None):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.rtsp_url = rtsp_url
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info(f"Câmera criada: IP={ip}, Porta={port}, Usuário={username}, RTSP_URL={rtsp_url}")
        self.onvif_cam = None
        self.cap = None
        self.connected = False

    def connect(self, timeout=10):
        try:
            if self.rtsp_url:
                self.cap = cv2.VideoCapture(self.rtsp_url)
                if self.cap.isOpened():
                    self.connected = True
                    self.logger.info(f"Conexão bem-sucedida com a câmera: {self.ip}")
                    return True
                else:
                    self.logger.error(f"Falha ao conectar à câmera RTSP: {self.rtsp_url}")
                    return False
            else:
                wsdl_dir = os.path.join(os.path.dirname(__file__), "wsdl")
                if not os.path.exists(wsdl_dir):
                    os.makedirs(wsdl_dir)
                if not get_onvif_wsdl_files(wsdl_dir):
                    self.logger.error("Falha ao preparar o diretório WSDL. A conexão ONVIF não pode prosseguir.")
                    return False
                self.logger.info(f"Diretório WSDL: {wsdl_dir}")
                
                session = requests.Session()
                session.timeout = timeout
                transport = Transport(session=session)
                
                self.logger.debug(f"Tentando criar ONVIFCamera com IP={self.ip}, Porta={self.port}, Usuário={self.username}")
                self.onvif_cam = ONVIFCamera(self.ip, self.port, self.username, self.password, wsdl_dir=wsdl_dir, transport=transport)
                self.logger.debug("ONVIFCamera criado com sucesso")
                
                media = self.onvif_cam.create_media_service()
                profiles = media.GetProfiles()
                if profiles:
                    profile = profiles[0]
                    stream_uri = media.GetStreamUri(
                        {'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': 'RTSP'},
                         'ProfileToken': profile.token})
                    self.rtsp_url = stream_uri.Uri
                    if self.username and self.password:
                        self.rtsp_url = self.rtsp_url.replace("rtsp://",
                                                            f"rtsp://{self.username}:{self.password}@")
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    if self.cap.isOpened():
                        self.connected = True
                        self.logger.info(f"Conexão bem-sucedida com a câmera: {self.ip}, RTSP_URL={self.rtsp_url}")
                        return True
                    else:
                        self.logger.error(f"Falha ao conectar à câmera ONVIF: {self.ip}")
                        return False
                else:
                    self.logger.error(f"Nenhum perfil encontrado para a câmera ONVIF: {self.ip}")
                    return False
        except Exception as e:
            self.logger.error(f"Erro ao conectar à câmera {self.ip}: {str(e)}")
            return False

    def get_frame(self):
        try:
            if self.connected and self.cap:
                ret, frame = self.cap.read()
                if ret:
                    return frame
                else:
                    self.connected = False
                    self.logger.warning(f"Falha ao obter frame da câmera: {self.ip}")
                    return None
            else:
                return None
        except Exception as e:
            self.logger.error(f"Erro ao obter frame da câmera {self.ip}: {e}")
            self.connected = False
            return None

    def disconnect(self):
        try:
            if self.cap:
                self.cap.release()
            self.connected = False
            self.logger.info(f"Câmera desconectada: {self.ip}")
        except Exception as e:
            self.logger.error(f"Erro ao desconectar câmera {self.ip}: {e}")