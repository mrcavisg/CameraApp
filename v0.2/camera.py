# Este código contém a classe Camera, responsável por gerenciar a conexão e leitura de frames das câmeras.

import cv2
import onvif
import queue
import threading
import time
import os
import sys
from config import MAX_FRAME_QUEUE_SIZE, MAX_RETRIES, RETRY_DELAY_BASE

class Camera:
    def __init__(self, ip, port, username, password, rtsp_url="", logger=None):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.rtsp_url = rtsp_url
        self.cam = None
        self.frame_queue = queue.Queue(maxsize=MAX_FRAME_QUEUE_SIZE)
        self.stop_event = threading.Event()
        self.thread = None
        self.connected = False
        self.cap = None
        self.logger = logger
        self.logger.info(f"Câmera criada: IP={self.ip}, Porta={self.port}, Usuário={self.username}, RTSP_URL={self.rtsp_url}")

    def connect(self):
        self.logger.info(f"Tentando conectar à câmera {self.ip}...")
        try:
            if not self.rtsp_url:
                self.logger.info(f"Descobrindo URL RTSP via ONVIF para {self.ip}")
                if getattr(sys, 'frozen', False):
                    wsdl_path = os.path.join(sys._MEIPASS, "onvif", "wsdl")
                    self.logger.info(f"Configurando caminho WSDL para: {wsdl_path}")
                    self.cam = onvif.ONVIFCamera(self.ip, self.port, self.username, self.password, wsdl_path=wsdl_path)
                else:
                    self.cam = onvif.ONVIFCamera(self.ip, self.port, self.username, self.password)
                media = self.cam.create_media_service()
                profiles = media.GetProfiles()
                token = profiles[0].token
                stream_uri = media.GetStreamUri(
                    {"StreamSetup": {"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}},
                     "ProfileToken": token}
                )
                self.rtsp_url = stream_uri.Uri
                self.logger.info(f"URL RTSP descoberta: {self.rtsp_url}")

            self.logger.info(f"Tentando conectar ao stream RTSP: {self.rtsp_url}")
            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 10)
            self.cap.set(cv2.CAP_PROP_FPS, 15)

            os.environ["OPENCV_FFMPEG_READ_TIMEOUT"] = "60000"
            os.environ["OPENCV_FFMPEG_READ_ATTEMPTS"] = "3"
            os.environ["OPENCV_FFMPEG_READ_TRANSPORT"] = "tcp"

            if not self.cap.isOpened():
                raise Exception(f"Não foi possível abrir a câmera RTSP: {self.rtsp_url}")

            ret, frame = self.cap.read()
            if not ret:
                raise Exception(f"Não foi possível ler o primeiro frame do stream RTSP: {self.rtsp_url}")

            self.connected = True
            self.thread = threading.Thread(target=self._read_frames, daemon=True)
            self.thread.start()
            self.logger.info(f"Conectado à câmera {self.ip} com sucesso")
            return True

        except Exception as e:
            self.logger.error(f"Erro ao conectar à câmera {self.ip}: {e}")
            self.connected = False
            return False

    def _read_frames(self):
        retry_count = 0
        while not self.stop_event.is_set():
            try:
                if not self.cap or not self.cap.isOpened():
                    self.logger.warning(f"VideoCapture não está aberto para {self.ip}. Tentando reconectar...")
                    if not self.connect():
                        retry_count += 1
                        if retry_count >= MAX_RETRIES:
                            self.logger.error(f"Excedeu o número máximo de tentativas ({MAX_RETRIES}) para reconectar à câmera {self.ip}.")
                            break
                        time.sleep(RETRY_DELAY_BASE ** retry_count)
                        continue
                    retry_count = 0

                ret, frame = self.cap.read()
                if ret:
                    retry_count = 0
                    if self.frame_queue.full():
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                    self.frame_queue.put(frame)
                else:
                    self.logger.warning(f"Falha na leitura, tentando reconectar a {self.ip} (tentativa {retry_count + 1}/{MAX_RETRIES})...")
                    self.cap.release()
                    if not self.connect():
                        retry_count += 1
                        if retry_count >= MAX_RETRIES:
                            self.logger.error(f"Excedeu o número máximo de tentativas ({MAX_RETRIES}) para reconectar à câmera {self.ip}.")
                            break
                        time.sleep(RETRY_DELAY_BASE ** retry_count)
                    else:
                        retry_count = 0
            except Exception as e:
                self.logger.error(f"Erro ao ler frames da câmera {self.ip}: {e}")
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    self.logger.error(f"Excedeu o número máximo de tentativas ({MAX_RETRIES}) para reconectar à câmera {self.ip}.")
                    break
                time.sleep(RETRY_DELAY_BASE ** retry_count)
        if self.cap:
            self.cap.release()
        self.logger.info(f"Thread de leitura da câmera {self.ip} encerrada.")
        self.connected = False

    def get_frame(self):
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None

    def disconnect(self):
        self.logger.info(f"Desconectando câmera {self.ip}...")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        if self.cap:
            self.cap.release()
        self.connected = False
        self.logger.info(f"Câmera {self.ip} desconectada.")