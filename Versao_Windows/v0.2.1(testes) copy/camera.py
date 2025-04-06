# camera.py (Atualizado com subprocess + FFmpeg para H.265)
import cv2
# from onvif import ONVIFCamera # ONVIF não será usado para conectar ao stream aqui
import logging
import os
import queue
import threading
import time
import subprocess # Importar subprocess
import numpy as np # Importar numpy
from tkinter import messagebox

# Se você não tiver um logger global, pode usar este
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO) # Configuração básica se não houver outra

class Camera:
    # __init__ permanece similar, mas não precisamos mais do objeto onvif_cam aqui
    def __init__(self, ip, port, username, password, rtsp_url="", camera_type="RTSP", logger=None):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.rtsp_url = rtsp_url # A URL RTSP é essencial agora
        self.camera_type = camera_type # Guardamos o tipo, mas ONVIF não será usado para conectar
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info(f"Câmera criada: IP={ip}, Porta={port}, Usuário={username}, RTSP_URL={rtsp_url}")

        # Dimensões do vídeo (IMPORTANTE: Ajuste se necessário ou implemente detecção)
        self.width = 2560
        self.height = 1440
        self.fps = 15 # Pode ser útil, mas não essencial para leitura do subprocess

        self.connected = False
        self.frame_queue = queue.Queue(maxsize=5)
        self.stop_event = threading.Event()
        self.thread = None
        self.ffmpeg_process = None # Referência para o processo FFmpeg

    # A descoberta ONVIF pode ser mantida como uma função separada se você ainda
    # precisar dela para *encontrar* a URL, mas não será usada no connect() principal.
    # def get_rtsp_url_from_onvif(self, timeout=10): ... (código anterior)

    def connect(self):
        """Prepara a câmera para iniciar a leitura via FFmpeg (inicia na thread)."""
        self.logger.info(f"Preparando conexão FFmpeg para {self.ip} (URL: {self.rtsp_url})...")
        if not self.rtsp_url:
            self.logger.error(f"URL RTSP não definida para a câmera {self.ip}. Não é possível conectar.")
            # Você poderia tentar chamar get_rtsp_url_from_onvif aqui se quisesse
            return False

        # A conexão real (iniciar o processo ffmpeg) será feita na thread _read_frames
        # para não bloquear a chamada inicial de connect. Apenas preparamos.
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._read_frames_ffmpeg, daemon=True)
        self.thread.start()
        # Consideramos 'conectado' quando a thread inicia. A thread lida com a falha.
        self.connected = True
        self.logger.info(f"Thread de leitura FFmpeg iniciada para {self.ip}.")
        return True

    def _read_frames_ffmpeg(self):
        """Lê frames usando FFmpeg via subprocess (executado em uma thread)."""
        self.logger.info(f"Thread _read_frames_ffmpeg iniciada para {self.ip}")

        # Calcula o tamanho de cada frame em bytes (BGR = 3 bytes por pixel)
        frame_size = self.width * self.height * 3
        retry_count = 0
        max_retries = 5

        while not self.stop_event.is_set():
            try:
                # Comando FFmpeg para decodificar e enviar frames BGR24 para stdout
                command = [
                    'ffmpeg',
                    '-loglevel', 'error', # Menos verboso, mude para 'warning' ou 'info' para debug
                    '-rtsp_transport', 'tcp', # Força TCP
                    '-i', self.rtsp_url, # URL de entrada
                    '-an', # Desabilita áudio
                    '-sn', # Desabilita legendas
                    '-f', 'rawvideo', # Formato de saída: vídeo bruto
                    '-pix_fmt', 'bgr24', # Formato de pixel que OpenCV entende
                    # '-s', f'{self.width}x{self.height}', # Opcional: Forçar tamanho (pode degradar)
                    # '-vf', f'fps={self.fps}', # Opcional: Forçar FPS
                    '-', # Saída para stdout
                ]

                self.logger.info(f"Iniciando processo FFmpeg para {self.ip}: {' '.join(command)}")
                # stderr=subprocess.PIPE para capturar erros do ffmpeg
                self.ffmpeg_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=frame_size*5) # Buffer maior

                while not self.stop_event.is_set():
                    # Lê exatamente o número de bytes de um frame do stdout do FFmpeg
                    in_bytes = self.ffmpeg_process.stdout.read(frame_size)

                    if not in_bytes:
                        self.logger.warning(f"FFmpeg para {self.ip}: Stream terminou ou erro de leitura (sem bytes).")
                        break # Sai do loop interno para tentar reiniciar o ffmpeg

                    if len(in_bytes) != frame_size:
                        self.logger.warning(f"FFmpeg para {self.ip}: Leitura incompleta do frame (esperado {frame_size}, recebido {len(in_bytes)}).")
                        # Tenta limpar o buffer ou simplesmente pula este frame incompleto
                        self.ffmpeg_process.stdout.flush() # Tenta limpar
                        continue # Pula para a próxima leitura

                    # Converte os bytes lidos em um array NumPy (frame OpenCV)
                    frame = np.frombuffer(in_bytes, np.uint8).reshape((self.height, self.width, 3))

                    # Coloca o frame na fila
                    if self.frame_queue.full():
                        self.frame_queue.get_nowait()
                    self.frame_queue.put(frame)
                    retry_count = 0 # Reseta contador de retentativa se a leitura foi OK
                    self.connected = True # Marca como conectado

                    # Verifica se o processo ffmpeg ainda está rodando
                    poll = self.ffmpeg_process.poll()
                    if poll is not None:
                        self.logger.error(f"Processo FFmpeg para {self.ip} terminou inesperadamente com código {poll}.")
                        break # Sai do loop interno para tentar reiniciar

            except Exception as e:
                self.logger.error(f"Exceção no loop de leitura FFmpeg para {self.ip}: {e}")
                # Erro pode ser ao iniciar Popen ou durante leitura/reshape

            finally:
                # Garante que o processo FFmpeg seja terminado se sairmos do loop interno
                if self.ffmpeg_process:
                    self.logger.info(f"Terminando processo FFmpeg para {self.ip}...")
                    self.ffmpeg_process.terminate() # Tenta terminar graciosamente
                    try:
                        # Espera um pouco e força o encerramento se necessário
                        self.ffmpeg_process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        self.logger.warning(f"Forçando encerramento do processo FFmpeg para {self.ip}")
                        self.ffmpeg_process.kill()
                    self.ffmpeg_process = None
                self.connected = False # Marca como desconectado ao sair do loop interno

            # Lógica de retentativa se o loop interno quebrou (e stop_event não foi setado)
            if not self.stop_event.is_set():
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.error(f"Máximo de tentativas de reinicio do FFmpeg atingido para {self.ip}. Desistindo.")
                    break # Sai do loop principal (while not self.stop_event.is_set())
                wait_time = 2 ** retry_count
                self.logger.info(f"Aguardando {wait_time}s antes de reiniciar FFmpeg para {self.ip}")
                time.sleep(wait_time)
            else:
                # Se o stop_event foi setado, sai do loop principal
                break

        # --- Fim do loop while not self.stop_event.is_set() ---
        self.connected = False
        self.logger.info(f"Thread _read_frames_ffmpeg finalizada para {self.ip}")


    def get_frame(self):
        """Obtém o frame mais recente da fila (não bloqueante)."""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None

    def disconnect(self):
        """Sinaliza para a thread parar e termina o processo FFmpeg."""
        self.logger.info(f"Solicitando desconexão da câmera {self.ip} (FFmpeg)...")
        self.stop_event.set() # Sinaliza para a thread _read_frames_ffmpeg parar

        if self.thread and self.thread.is_alive():
            self.logger.info(f"Aguardando thread FFmpeg de {self.ip} finalizar...")
            self.thread.join(timeout=3) # Espera pela thread (que deve terminar o ffmpeg)

        # Garante que o processo seja terminado mesmo que a thread falhe
        if self.ffmpeg_process:
            self.logger.warning(f"Thread FFmpeg de {self.ip} não finalizou a tempo ou já havia terminado. Garantindo que o processo FFmpeg seja encerrado.")
            try:
                 if self.ffmpeg_process.poll() is None: #Se ainda estiver rodando
                    self.ffmpeg_process.terminate()
                    self.ffmpeg_process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()
            except Exception as e:
                 self.logger.error(f"Erro ao tentar finalizar processo FFmpeg na desconexão: {e}")
            finally:
                 self.ffmpeg_process = None


        self.connected = False
        self.thread = None
        # Limpa a fila ao desconectar para evitar frames antigos
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        self.logger.info(f"Recursos da câmera {self.ip} (FFmpeg) liberados.")