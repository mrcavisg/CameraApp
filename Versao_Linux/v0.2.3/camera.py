# camera.py (CORRIGIDO - v2 com Threading, Queue, TCP, Timeouts)
import cv2
import logging
import os
import queue
import threading
import time
from tkinter import messagebox
import sys

# Tenta importar ONVIFCamera, define como None se falhar
try:
    from onvif import ONVIFCamera
except ImportError:
    ONVIFCamera = None
    print("AVISO: Biblioteca 'onvif-zeep' não encontrada. Funcionalidade ONVIF desabilitada.", file=sys.stderr)

# Obtém o logger (idealmente passado do app principal)
try:
    # Tenta pegar do config para consistência
    from config import LOGGER_NAME
except (ImportError, NameError):
    LOGGER_NAME = "CameraApp_Fallback" # Fallback
logger_fallback = logging.getLogger(LOGGER_NAME)
# Garante uma config mínima se logger não for configurado globalmente
if not logger_fallback.hasHandlers():
    logging.basicConfig(level=logging.INFO)

class Camera:
    def __init__(self, ip, port, username, password, rtsp_url="", camera_type="RTSP", logger_instance=None): # Aceita logger_instance
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.rtsp_url = rtsp_url
        self.logger = logger_instance or logger_fallback # Usa logger passado ou fallback
        # Lógica para definir camera_type baseada na URL e no tipo passado
        final_camera_type = camera_type
        if not rtsp_url and camera_type == "RTSP":
            final_camera_type = "ONVIF"
            self.logger.warning(f"URL RTSP vazia para {ip}, assumindo tipo ONVIF.")
        elif rtsp_url and camera_type == "ONVIF":
            final_camera_type = "RTSP"
            self.logger.warning(f"URL RTSP fornecida para {ip}, tratando como tipo RTSP.")
        self.camera_type = final_camera_type

        self.logger.info(f"Câmera criada: IP={ip}, Porta={port}, Usuário={username}, Tipo={self.camera_type}, RTSP_URL={rtsp_url}")

        # Atributos para conexão e leitura
        self.onvif_cam = None
        self.cap = None
        self.connected = False
        self.frame_queue = queue.Queue(maxsize=5) # Fila para frames
        self.stop_event = threading.Event() # Sinalizador para parar thread
        self.thread = None # Thread de leitura

    def get_rtsp_url_from_onvif(self, timeout=10):
        """Obtém a URL RTSP usando ONVIF."""
        if ONVIFCamera is None:
            self.logger.error("Biblioteca ONVIF não está disponível para descoberta.")
            return None

        self.logger.info(f"Descobrindo URL RTSP via ONVIF para {self.ip}:{self.port}")
        try:
            self.onvif_cam = ONVIFCamera(
                self.ip, self.port, self.username, self.password,
                no_cache=True, adjust_time=True, connect_timeout=timeout
            )
            # Verifica se a conexão ONVIF foi bem-sucedida (necessário?)
            # A chamada create_media_service geralmente já tenta conectar
            # self.logger.debug("Verificando serviços ONVIF...")
            # self.onvif_cam.ver10.device.GetServices({'IncludeCapability': False})
            # self.logger.debug("Serviços ONVIF verificados.")

            media = self.onvif_cam.create_media_service()
            profiles = media.GetProfiles()
            if profiles:
                profile = profiles[0]
                stream_uri_params = {
                    'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}},
                    'ProfileToken': profile.token
                }
                stream_uri = media.GetStreamUri(stream_uri_params)
                discovered_rtsp_url = stream_uri.Uri
                self.logger.info(f"URL RTSP descoberta via ONVIF: {discovered_rtsp_url}")
                # Opcional: Adicionar credenciais (testar sem primeiro)
                # if self.username and self.password and f"{self.username}:{self.password}@" not in discovered_rtsp_url:
                #     discovered_rtsp_url = discovered_rtsp_url.replace("rtsp://", f"rtsp://{self.username}:{self.password}@")
                return discovered_rtsp_url
            else:
                self.logger.error(f"Nenhum perfil ONVIF encontrado para a câmera: {self.ip}")
                return None
        except Exception as e:
            self.logger.error(f"Erro durante descoberta ONVIF para {self.ip}: {str(e)}", exc_info=True)
            return None

    def connect(self, timeout_open=10000, timeout_read=15000):
        """Tenta conectar à câmera e inicia a thread de leitura."""
        self.logger.debug(f"Iniciando connect() para {self.ip} (Tipo: {self.camera_type})...")
        self.stop_event.clear()

        temp_rtsp_url = self.rtsp_url

        # Tenta descobrir URL se for ONVIF e não tiver uma
        if self.camera_type == "ONVIF" and not temp_rtsp_url:
            temp_rtsp_url = self.get_rtsp_url_from_onvif()
            if not temp_rtsp_url:
                self.logger.error(f"Falha ao obter URL RTSP via ONVIF para {self.ip}.")
                self.connected = False
                return False

        if not temp_rtsp_url:
             self.logger.error(f"URL RTSP final não disponível para {self.ip}.")
             self.connected = False
             return False

        # Adiciona ;transport=tcp
        url_para_conectar = temp_rtsp_url
        if ";transport=tcp" not in temp_rtsp_url.lower():
             url_para_conectar += ";transport=tcp"

        self.logger.info(f"Tentando cv2.VideoCapture com: {url_para_conectar}")

        try:
            # Libera o cap anterior se existir
            if self.cap:
                self.cap.release()
                self.logger.debug("VideoCapture anterior liberado.")

            self.cap = cv2.VideoCapture(url_para_conectar, cv2.CAP_FFMPEG)

            # Importa constantes de config.py ou usa defaults
            try: from config import CAMERA_CONNECT_TIMEOUT_CV_OPEN, CAMERA_CONNECT_TIMEOUT_CV_READ, CAMERA_FRAME_QUEUE_SIZE
            except ImportError: CAMERA_CONNECT_TIMEOUT_CV_OPEN, CAMERA_CONNECT_TIMEOUT_CV_READ, CAMERA_FRAME_QUEUE_SIZE = timeout_open, timeout_read, 5

            self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, CAMERA_CONNECT_TIMEOUT_CV_OPEN)
            self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, CAMERA_CONNECT_TIMEOUT_CV_READ)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3) # Buffer menor

            if not self.cap.isOpened():
                # Tenta obter o backend name se possível, mas trata erro
                backend_name = "N/A"
                try: backend_name = self.cap.getBackendName()
                except Exception: pass
                error_message = f"Falha ao abrir stream RTSP com OpenCV: {url_para_conectar} (Backend: {backend_name})"
                self.logger.error(error_message)
                self.connected = False
                if self.cap: self.cap.release(); self.cap = None
                return False

            self.logger.info(f"cv2.VideoCapture aberto com sucesso para: {url_para_conectar}")
            self.connected = True # MARCA COMO CONECTADO AQUI
            self.rtsp_url = temp_rtsp_url # Atualiza URL interna

            # Inicia a thread _read_frames
            # Garante que a thread anterior parou antes de iniciar nova
            if self.thread and self.thread.is_alive():
                self.logger.warning(f"Thread antiga para {self.ip} ainda ativa ao reconectar. Tentando parar...")
                self.stop_event.set()
                self.thread.join(timeout=1)

            self.stop_event.clear() # Limpa evento para nova thread
            self.thread = threading.Thread(target=self._read_frames, name=f"CamReader_{self.ip}", daemon=True)
            self.thread.start()
            self.logger.info(f"Conectado à câmera {self.ip} e thread de leitura iniciada.")
            return True

        except Exception as e:
            self.logger.error(f"Exceção ao conectar à câmera {self.ip} com OpenCV: {str(e)}", exc_info=True)
            if self.cap: self.cap.release(); self.cap = None
            self.connected = False
            return False

    def _read_frames(self):
        """Lê frames da câmera em loop (executado em uma thread)."""
        self.logger.info(f"Thread _read_frames iniciada para {self.ip}")
        # Importa constantes de config.py ou usa defaults
        try: from config import CAMERA_MAX_RETRIES, CAMERA_RETRY_DELAY_BASE, CAMERA_MAX_RETRY_WAIT, CAMERA_CONSECUTIVE_READ_FAILURES_LIMIT
        except ImportError: CAMERA_MAX_RETRIES, CAMERA_RETRY_DELAY_BASE, CAMERA_MAX_RETRY_WAIT, CAMERA_CONSECUTIVE_READ_FAILURES_LIMIT = 5, 2, 60, 10

        retry_count = 0
        consecutive_read_failures = 0

        while not self.stop_event.is_set():
            # Verifica conexão ANTES de tentar ler
            if not self.connected or self.cap is None or not self.cap.isOpened():
                self.logger.warning(f"Câmera {self.ip} não conectada na thread, tentando reconectar...")
                if self.cap: self.cap.release(); self.cap = None # Garante liberação

                # Tenta reconectar
                if self.connect(): # Chama o connect da classe (que tentará abrir e iniciar a thread novamente - CUIDADO COM RECURSÃO INFINITA SE FALHAR MUITO RÁPIDO)
                                   # A chamada connect agora inicia a thread, então talvez a lógica aqui precise ser ajustada
                                   # Melhor: A thread só deve LER. Se falhar, marca como desconectado e a thread principal decide reconectar.
                                   # --- REVISÃO DA LÓGICA DE RECONEXÃO ---
                    self.logger.info(f"Reconexão bem sucedida para {self.ip} dentro da thread.")
                    retry_count = 0
                    consecutive_read_failures = 0
                    # Não precisa de 'continue' aqui, pois o loop while verificará 'connected'
                else:
                    # Falha na reconexão
                    retry_count += 1
                    if retry_count >= CAMERA_MAX_RETRIES:
                        self.logger.error(f"Máximo de tentativas ({CAMERA_MAX_RETRIES}) de reconexão atingido para {self.ip}. Thread será encerrada.")
                        self.connected = False
                        self.stop_event.set() # Para a thread
                        break # Sai do loop while
                    wait_time = min(CAMERA_RETRY_DELAY_BASE ** retry_count, CAMERA_MAX_RETRY_WAIT)
                    self.logger.info(f"Aguardando {wait_time}s antes da próxima tentativa de reconexão para {self.ip} ({retry_count}/{CAMERA_MAX_RETRIES})")
                    # Espera pelo tempo definido OU até stop_event ser sinalizado
                    if self.stop_event.wait(timeout=wait_time):
                        self.logger.info(f"Stop event recebido durante espera de reconexão para {self.ip}.")
                        break # Sai do loop while se stop foi chamado
                # Se chegou aqui após falha na reconexão e não saiu, volta ao início do loop
                continue

            # Se conectado, tenta ler o frame
            try:
                ret, frame = self.cap.read()
                if ret:
                    consecutive_read_failures = 0 # Reseta falhas
                    # Coloca na fila
                    if self.frame_queue.full():
                        self.frame_queue.get_nowait() # Descarta antigo
                    self.frame_queue.put(frame)
                    # self.logger.debug(f"Frame lido e adicionado à fila para {self.ip}") # Log muito verboso
                    # Pequena pausa para ceder CPU
                    time.sleep(0.01) # Ajuste conforme necessário
                else:
                    # Falha na leitura (ret == False)
                    consecutive_read_failures += 1
                    self.logger.warning(f"Falha na leitura do frame (ret=False) para {self.ip} (Falha #{consecutive_read_failures})")
                    if consecutive_read_failures >= CAMERA_CONSECUTIVE_READ_FAILURES_LIMIT:
                         self.logger.error(f"Limite de falhas de leitura seguidas ({CAMERA_CONSECUTIVE_READ_FAILURES_LIMIT}) atingido para {self.ip}. Marcando como desconectado.")
                         self.connected = False # Marca como desconectado, a próxima iteração tentará reconectar
                         if self.cap: self.cap.release(); self.cap = None
                    else:
                         time.sleep(0.5) # Espera um pouco antes de tentar ler de novo

            except Exception as e:
                self.logger.error(f"Exceção na leitura do frame para {self.ip}: {e}", exc_info=True)
                self.connected = False # Marca como desconectado
                if self.cap: self.cap.release(); self.cap = None
                # A próxima iteração tentará reconectar

        # --- Fim do loop while not self.stop_event.is_set() ---
        # Garante limpeza ao sair da thread
        if self.cap:
            try: self.cap.release()
            except Exception as e: self.logger.error(f"Erro ao liberar cap no final da thread {self.ip}: {e}")
            finally: self.cap = None
        self.connected = False
        self.logger.info(f"Thread _read_frames finalizada para {self.ip}")


    def get_frame(self):
        """Obtém o frame mais recente da fila (não bloqueante)."""
        try:
            # Verifica se a thread está ativa
            if self.thread and not self.thread.is_alive() and self.connected:
                 self.logger.warning(f"Thread para {self.ip} não está ativa, mas câmera marcada como conectada. Forçando disconnect.")
                 self.disconnect(); return None

            # Tenta obter da fila
            return self.frame_queue.get_nowait()

        except queue.Empty:
            # É normal a fila estar vazia às vezes
            return None
        except Exception as e:
             # Loga outros erros inesperados
             self.logger.error(f"Erro inesperado em get_frame para {self.ip}: {e}", exc_info=True)
             return None


    def disconnect(self):
        """Sinaliza para a thread parar e libera os recursos."""
        if self.stop_event.is_set() and not self.connected and self.thread is None:
            # Se já foi chamado e parece desconectado, evita trabalho redundante
            # self.logger.debug(f"Disconnect chamado para {self.ip}, mas já parece desconectado.")
            return

        self.logger.info(f"Solicitando desconexão da câmera {self.ip}...")
        self.connected = False # Marca como desconectado imediatamente
        self.stop_event.set() # Sinaliza para a thread parar

        thread_to_join = self.thread
        cap_to_release = self.cap
        self.thread = None # Limpa referência
        self.cap = None # Limpa referência

        # Espera a thread terminar
        if thread_to_join and thread_to_join.is_alive():
            self.logger.debug(f"Aguardando thread de {self.ip} finalizar...")
            thread_to_join.join(timeout=2) # Espera um pouco
            if thread_to_join.is_alive():
                self.logger.warning(f"Timeout ao aguardar thread de {self.ip} em disconnect.")

        # Garante liberação do cap (pode ser redundante se a thread limpou, mas seguro)
        if cap_to_release:
            try:
                cap_to_release.release()
                self.logger.debug(f"cv2.VideoCapture liberado (verificação final) para {self.ip} em disconnect.")
            except Exception as e:
                self.logger.error(f"Erro ao liberar self.cap (verificação final) em disconnect para {self.ip}: {e}")

        # Limpa a fila
        while not self.frame_queue.empty():
            try: self.frame_queue.get_nowait()
            except queue.Empty: break
        self.logger.info(f"Recursos da câmera {self.ip} liberados.")

# Fim da classe Camera