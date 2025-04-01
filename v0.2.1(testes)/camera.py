# camera.py

import cv2
# Tenta importar ONVIFCamera e Transport, define como None se falhar
try:
    from onvif import ONVIFCamera
    from zeep.transports import Transport
except ImportError:
    ONVIFCamera = None
    Transport = None
    print("AVISO: Biblioteca 'onvif-zeep' não encontrada. Funcionalidade ONVIF desabilitada.", file=sys.stderr)

import logging
import os
import sys # para print de aviso
# from wsdl_utils import get_onvif_wsdl_files # Não mais necessário
# import requests # Não parece estar sendo usado

# Importa re e urllib para formatação de URL
import re
from urllib.parse import urlparse, urlunparse

# Obtém o logger (usando o mesmo nome da app se possível)
try:
    from config import APP_NAME
    logger_name = APP_NAME
except (ImportError, NameError):
    logger_name = "CameraModuleFallback"
logger = logging.getLogger(logger_name)

class Camera:
    def __init__(self, ip, port, username, password, rtsp_url="", logger=None):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.rtsp_url = rtsp_url # Pode ser preenchido aqui (RTSP direto) ou descoberto (ONVIF)
        self.logger = logger or logging.getLogger(logger_name)
        self.logger.info(f"Câmera criada: IP={ip}, Porta={port}, Usuário={username}, RTSP_URL={rtsp_url}")
        self.onvif_cam = None # Objeto da câmera ONVIF
        self.cap = None # Objeto VideoCapture do OpenCV
        self.connected = False # Estado da conexão

    def connect(self, timeout=10):
        """Tenta conectar à câmera via RTSP direto ou via ONVIF para descobrir RTSP."""
        self.logger.debug(f"Iniciando connect() para {self.ip}...")
        self.disconnect() # Garante que está desconectado antes de tentar conectar
        try:
            # --- Tenta Conexão RTSP Direta ---
            if self.rtsp_url:
                self.logger.debug(f"Tentando conexão RTSP direta: {self.rtsp_url}")
                self.cap = cv2.VideoCapture(self.rtsp_url)
                if self.cap.isOpened():
                    self.connected = True
                    self.logger.info(f"Conexão RTSP direta OK: {self.rtsp_url}")
                    return True
                else:
                    self.logger.error(f"Falha ao abrir stream RTSP direto: {self.rtsp_url}")
                    self.cap = None # Garante que cap é None se falhou
                    return False
            # --- Tenta Conexão ONVIF ---
            else:
                # Verifica disponibilidade das bibliotecas
                if ONVIFCamera is None or Transport is None:
                     self.logger.error("ONVIF/Zeep não carregado. Não é possível conectar via ONVIF.")
                     return False

                self.logger.info(f"Tentando conexão ONVIF com {self.ip}:{self.port}")
                transport = Transport(timeout=timeout)
                try:
                    # OMITIR wsdl_dir para usar o padrão da biblioteca
                    self.onvif_cam = ONVIFCamera(
                        self.ip, self.port, self.username, self.password,
                        transport=transport,
                        no_cache=True # Força recarregar WSDLs do padrão (útil p/ debug)
                    )
                    self.logger.debug(f"ONVIFCamera inicializada para {self.ip}.")
                except Exception as onvif_init_err:
                     self.logger.error(f"Falha inicializar ONVIFCamera {self.ip}: {onvif_init_err}", exc_info=True)
                     return False

                # Obtém serviços e perfis (pode falhar aqui se autenticação/conexão falhar)
                try:
                    # Garante que devicemgmt foi criado (às vezes __init__ não garante)
                    if not hasattr(self.onvif_cam, 'devicemgmt') or not self.onvif_cam.devicemgmt:
                         self.logger.debug("Criando serviço devicemgmt explicitamente...")
                         self.onvif_cam.create_devicemgmt_service()

                    # Obtém informações do dispositivo (útil para log)
                    try:
                         dev_info = self.onvif_cam.devicemgmt.GetDeviceInformation()
                         self.logger.info(f"Info ONVIF {self.ip}: {dev_info.Manufacturer} {dev_info.Model} FW:{dev_info.FirmwareVersion}")
                    except Exception as dev_info_err:
                         self.logger.warning(f"Não foi possível obter info do dispositivo ONVIF {self.ip}: {dev_info_err}")

                    # Cria serviço de Mídia
                    self.logger.debug("Criando serviço de mídia...")
                    media_service = self.onvif_cam.create_media_service()
                    # Obtém Perfis
                    self.logger.debug("Obtendo perfis de mídia...")
                    profiles = media_service.GetProfiles()
                    self.logger.debug(f"Perfis obtidos para {self.ip}: {len(profiles) if profiles else 'Nenhum'}")

                except Exception as service_err:
                     self.logger.error(f"Erro obter serviços/perfis ONVIF {self.ip}: {service_err}", exc_info=True)
                     return False

                # --- Processa os Perfis ---
                if profiles:
                    uri = None; profile_token = None
                    self.logger.info(f"Analisando {len(profiles)} perfis ONVIF para {self.ip}...")

                    for idx, profile in enumerate(profiles):
                        profile_token = getattr(profile, 'token', f'NO_TOKEN_{idx}')
                        profile_name = getattr(profile, 'Name', f'NO_NAME_{idx}')
                        self.logger.info(f"--- Analisando Perfil {idx} ---")
                        self.logger.info(f"  Token: {profile_token}"); self.logger.info(f"  Nome: {profile_name}")
                        # Logar detalhes extras
                        try:
                            if hasattr(profile, 'VideoEncoderConfiguration') and profile.VideoEncoderConfiguration:
                                 ve = profile.VideoEncoderConfiguration
                                 res = getattr(ve, 'Resolution', None)
                                 res_str = f"{getattr(res, 'Width', '?')}x{getattr(res, 'Height', '?')}" if res else "?"
                                 self.logger.info(f"  VideoEncoder: Codec={getattr(ve, 'Encoding', '?')}, Res={res_str}, FPS={getattr(getattr(ve, 'RateControl', None), 'FrameRateLimit', '?')}, Qual={getattr(ve, 'Quality', '?')}")
                            else: self.logger.info("  VideoEncoder: Não encontrado.")
                        except Exception as log_err: self.logger.warning(f"  Erro logar detalhes perfil {profile_token}: {log_err}")

                        # Tenta encontrar URI RTSP
                        try:
                            if hasattr(profile, 'rtsp') and profile.rtsp and hasattr(profile.rtsp, 'Uri') and profile.rtsp.Uri:
                                potential_uri = profile.rtsp.Uri
                                if potential_uri:
                                    uri = potential_uri
                                    self.logger.info(f"  >>>> URI RTSP encontrada: {uri} <<<<")
                                    break # Usa a primeira encontrada
                                else: self.logger.info("  Uri encontrada mas vazia/None.")
                            else: self.logger.info("  Estrutura rtsp.Uri não encontrada.")
                        except Exception as e_prof: self.logger.warning(f"  Erro acessar RTSP perfil {profile_token}: {e_prof}"); continue
                    # --- Fim do loop for profile ---

                    if uri:
                        # Formata URL e tenta conectar com OpenCV
                        try:
                             parsed_uri = urlparse(uri); netloc = parsed_uri.hostname; user_pass = ""
                             if self.username: user_pass = self.username
                             if self.password: user_pass += f":{self.password}"
                             if user_pass: netloc = f"{user_pass}@{netloc}"
                             if parsed_uri.port: netloc += f":{parsed_uri.port}"
                             self.rtsp_url = urlunparse((parsed_uri.scheme, netloc, parsed_uri.path, parsed_uri.params, parsed_uri.query, parsed_uri.fragment))
                             self.logger.info(f"Usando URL RTSP formatada perfil {profile_token}: {self.rtsp_url}")
                        except Exception as url_err: self.logger.error(f"Erro formatar URL '{uri}': {url_err}", exc_info=True); return False

                        self.cap = cv2.VideoCapture(self.rtsp_url)
                        if self.cap.isOpened():
                            self.connected = True; self.logger.info(f"ONVIF->RTSP ok: {self.ip}"); return True
                        else:
                            self.logger.error(f"Falha abrir stream RTSP descoberto: {self.rtsp_url}"); self.cap = None; return False
                    else:
                        # Se URI não encontrada, tenta GetStreamUri como fallback (OPCIONAL)
                        self.logger.warning(f"Nenhuma URI RTSP nos perfis. Tentando GetStreamUri (pode não funcionar)...")
                        uri_from_get = None
                        for profile in profiles: # Itera novamente
                            profile_token = getattr(profile, 'token', None)
                            if not profile_token: continue
                            try:
                                req = media_service.create_type('GetStreamUri')
                                req.ProfileToken = profile_token
                                req.StreamSetup = {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}}
                                stream_uri_obj = media_service.GetStreamUri(req)
                                if stream_uri_obj and hasattr(stream_uri_obj, 'Uri') and stream_uri_obj.Uri:
                                     uri_from_get = stream_uri_obj.Uri
                                     self.logger.info(f"URI RTSP obtida via GetStreamUri p/ {profile_token}: {uri_from_get}")
                                     break # Usa a primeira encontrada
                            except Exception as get_uri_err: self.logger.warning(f"Falha GetStreamUri p/ {profile_token}: {get_uri_err}")

                        if uri_from_get:
                            # Formata e tenta conectar com a URI obtida via GetStreamUri
                            try:
                                 parsed_uri=urlparse(uri_from_get); netloc=parsed_uri.hostname; user_pass=""
                                 if self.username: user_pass=self.username
                                 if self.password: user_pass+=f":{self.password}"
                                 if user_pass: netloc=f"{user_pass}@{netloc}"
                                 if parsed_uri.port: netloc+=f":{parsed_uri.port}"
                                 self.rtsp_url = urlunparse((parsed_uri.scheme, netloc, parsed_uri.path, parsed_uri.params, parsed_uri.query, parsed_uri.fragment))
                                 self.logger.info(f"Usando URL RTSP formatada (GetStreamUri) p/ {profile_token}: {self.rtsp_url}")
                            except Exception as url_err: self.logger.error(f"Erro formatar URL (GetStreamUri) '{uri_from_get}': {url_err}", exc_info=True); return False

                            self.cap = cv2.VideoCapture(self.rtsp_url)
                            if self.cap.isOpened():
                                 self.connected=True; self.logger.info(f"ONVIF->GetStreamUri->RTSP ok: {self.ip}"); return True
                            else: self.logger.error(f"Falha abrir stream RTSP (GetStreamUri): {self.rtsp_url}"); self.cap=None; return False
                        else:
                             # Falhou em ambos os métodos
                             self.logger.error(f"Nenhuma URI RTSP encontrada (GetProfiles/GetStreamUri) para {self.ip}.")
                             return False
                else:
                    self.logger.error(f"Nenhum perfil ONVIF retornado por {self.ip}."); return False

        except Exception as e:
            # Captura qualquer outra exceção durante a conexão
            self.logger.error(f"Erro EXCEPCIONAL durante connect() para {self.ip}: {e}", exc_info=True)
            self.disconnect() # Garante que desconecte em caso de erro
            return False

    def get_frame(self):
        """Lê e retorna um frame da câmera se conectada."""
        try:
            if self.connected and self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    return frame
                else:
                    self.logger.warning(f"Falha ao ler frame (ret=False) da câmera {self.ip}. Desconectando.")
                    self.disconnect() # Chama disconnect para limpeza
                    return None
            else:
                # self.logger.debug(f"get_frame: Não conectado ou sem cap para {self.ip}") # Debug
                return None
        except Exception as e:
            self.logger.error(f"Erro EXCEPCIONAL em get_frame para {self.ip}: {e}", exc_info=True)
            self.disconnect() # Força desconexão
            return None

    def disconnect(self):
        """Libera os recursos da câmera."""
        try:
            was_connected = self.connected # Guarda estado anterior
            self.connected = False # Define como falso primeiro
            if self.cap:
                self.logger.debug(f"Liberando cv2.VideoCapture para {self.ip}...")
                self.cap.release()
                self.cap = None
                self.logger.debug(f"cv2.VideoCapture liberado para {self.ip}.")
            # Limpa referência à câmera ONVIF também? Pode ser útil.
            self.onvif_cam = None
            if was_connected: # Loga só se estava conectado antes
                 self.logger.info(f"Câmera desconectada: {self.ip}")
        except Exception as e:
            self.logger.error(f"Erro ao desconectar câmera {self.ip}: {e}")
            # Garante que estado e cap estejam limpos mesmo com erro
            self.connected = False
            self.cap = None
            self.onvif_cam = None

# Fim da classe Camera