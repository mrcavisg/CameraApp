# app.py (Completo, com load_cameras/start_cameras definidos na classe)

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import re
import numpy as np
import cv2
from PIL import Image, ImageTk
# Importa Camera e as funções de utils CORRIGIDAS
from camera import Camera
# !!! GARANTA QUE utils.py É A VERSÃO CORRIGIDA QUE ACEITA logger=None !!!
from utils import save_cameras, load_cameras
# Importa de config
# Tratamento caso config.py não exista ou APP_NAME não esteja definido
try:
    from config import FRAME_UPDATE_INTERVAL, APP_NAME
    logger_name = APP_NAME
except (ImportError, NameError):
    FRAME_UPDATE_INTERVAL = 30 # Default
    APP_NAME = "CameraApp_Fallback" # Nome fallback
    logger_name = APP_NAME
    print("AVISO: Não foi possível importar de config.py. Usando valores padrão.", file=sys.stderr)

from wsdiscovery import WSDiscovery
from wsdiscovery.service import Service
# Tenta importar ONVIFCamera, mas trata se falhar (ex: dependência faltando)
try:
    from onvif import ONVIFCamera
except ImportError:
    ONVIFCamera = None
    print("AVISO: Biblioteca 'onvif-zeep' não encontrada ou não pode ser importada. Funcionalidade ONVIF desabilitada.", file=sys.stderr)

import logging
import threading
import sys # Importado para fallback do config

# Define o logger
logger = logging.getLogger(logger_name)

# Classe QName (com correções para wsdiscovery)
# Em app.py - Substitua a definição da classe SimpleQName por esta:

# Em app.py - Substitua TODA a classe SimpleQName por esta:

# Classe para simular o comportamento do QName (COM TODOS os métodos necessários)
class SimpleQName:
    def __init__(self, namespace, local_part):
        self.namespace = namespace
        self.local_part = local_part
        # Obtém o logger global definido anteriormente no script
        # Garantindo que logger_name exista globalmente ou usando fallback
        self.logger = logging.getLogger(logger_name if 'logger_name' in globals() else __name__)
        # self.logger.debug(f"SimpleQName criado: ns={namespace}, local={local_part}") # Debug opcional

    def getNamespace(self):
        # self.logger.debug(f"SimpleQName.getNamespace() -> {self.namespace}")
        return self.namespace

    def getLocalname(self):
        # self.logger.debug(f"SimpleQName.getLocalname() -> {self.local_part}")
        return self.local_part

    def getNamespacePrefix(self):
        # self.logger.debug("SimpleQName.getNamespacePrefix() -> None")
        return None # Retorna None como antes

    def getFullname(self): # <<< GARANTA QUE ESTE MÉTODO ESTÁ AQUI >>>
        # Adiciona um print de diagnóstico para ter certeza que está sendo chamado
        print(f"--- DEBUG: Chamando getFullname() para ns={self.namespace}, local={self.local_part} ---")
        fullname = f"{{{self.namespace}}}{self.local_part}"
        # self.logger.debug(f"SimpleQName.getFullname() -> {fullname}")
        return fullname

class CameraApp:
    def __init__(self, root, logger):
        self.logger = logger # Usa o logger passado de main.py
        self.logger.info("Inicializando CameraApp...")
        self.root = root
        self.root.title(f"{logger_name} by CFA TECH")
        self.root.geometry("1280x720")
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)
        self.cameras = []
        self.labels = []
        self.camera_list_window = None
        self.aspect_ratios = []
        self.running = True

        style = ttk.Style()
        style.theme_use("clam")

        self.create_menu()
        self.create_widgets() # Chama load, start, create_labels, update
        self.root.update_idletasks()
        self.center_window(self.root)

    def center_window(self, window):
        try:
            if not window.winfo_exists(): return
            window.update_idletasks()
            width = window.winfo_width(); height = window.winfo_height()
            screen_width = window.winfo_screenwidth(); screen_height = window.winfo_screenheight()
            x = max(0, (screen_width // 2) - (width // 2))
            y = max(0, (screen_height // 2) - (height // 2))
            window.geometry(f"{width}x{height}+{x}+{y}")
            if window.state() == 'normal': # Só deiconify se não estiver normal (ex: iconic)
                 window.deiconify()
        except tk.TclError as e:
             if "application has been destroyed" not in str(e):
                  self.logger.error(f"Erro Tcl ao centralizar janela: {e}")
        except Exception as e:
            self.logger.error(f"Erro inesperado ao centralizar janela: {e}", exc_info=True)

    def create_menu(self):
        try:
            menubar = tk.Menu(self.root)
            self.root.config(menu=menubar)
            opcoes_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Opções", menu=opcoes_menu)
            opcoes_menu.add_command(label="Gerenciar Câmeras", command=self.open_camera_list_window)
            opcoes_menu.add_separator()
            opcoes_menu.add_command(label="Minimizar", command=self.minimize_window)
            opcoes_menu.add_command(label="Sair", command=self.close_window)
            self.logger.info("Menu criado.")
        except Exception as e:
            self.logger.error(f"Erro ao criar menu: {e}", exc_info=True)

    def create_widgets(self):
        try:
            self.frame_container = tk.Frame(self.root)
            self.frame_container.pack(expand=True, fill=tk.BOTH)

            # *** CHAMADAS PARA OS MÉTODOS QUE PRECISAM EXISTIR ***
            self.load_cameras() # Chama o método load_cameras DESTA classe
            self.start_cameras() # Chama o método start_cameras DESTA classe
            # *****************************************************

            self.create_video_labels()
            self.update_frames() # Inicia o loop de atualização
            self.logger.info("Widgets criados e câmeras iniciadas.")
        except AttributeError as e:
             self.logger.critical(f"Erro Crítico: Método faltando! '{e.name}' não está definido em CameraApp. Erro: {e}", exc_info=True)
             messagebox.showerror("Erro Crítico de Código", f"Método necessário '{e.name}' não encontrado.\nVerifique o arquivo app.py.")
             self.close_window()
        except Exception as e:
            self.logger.error(f"Erro fatal ao criar widgets ou iniciar câmeras: {e}", exc_info=True)
            messagebox.showerror("Erro de Inicialização", f"Falha ao criar interface ou iniciar câmeras:\n{e}")
            self.close_window()

    # --- Métodos load_cameras e start_cameras DENTRO da classe ---
    # <<< ESTAS DEFINIÇÕES PRECISAM ESTAR AQUI >>>
    def load_cameras(self):
        """ Carrega câmeras do arquivo JSON usando a função de utils.py """
        try:
            # Chama a função load_cameras importada de utils.py
            # Passa o logger da instância da classe CameraApp
            # !! GARANTA QUE utils.py TEM load_cameras(logger=None) !!
            loaded_camera_objects = load_cameras(logger=self.logger) # Chama a função de utils

            self.cameras = [] # Limpa a lista atual
            # Adiciona apenas objetos Camera válidos
            for cam_obj in loaded_camera_objects:
                 if isinstance(cam_obj, Camera):
                      self.cameras.append(cam_obj)
                 else:
                      self.logger.warning(f"Ignorando objeto inválido carregado do JSON: {type(cam_obj)}")
            self.logger.info(f"{len(self.cameras)} câmeras carregadas e prontas na instância CameraApp.")
        except TypeError as te:
            # Erro específico se utils.load_cameras não aceitar 'logger'
            self.logger.critical(f"Erro de Tipo ao chamar utils.load_cameras: {te}. Verifique se utils.py está atualizado!", exc_info=True)
            messagebox.showerror("Erro Crítico de Código", f"Erro ao chamar utils.load_cameras:\n{te}\n\nVerifique se o arquivo utils.py está correto e aceita o argumento 'logger'.")
            self.cameras = []
        except Exception as e:
            self.logger.error(f"Erro fatal ao carregar câmeras (em app.load_cameras): {e}", exc_info=True)
            messagebox.showerror("Erro ao Carregar", f"Não foi possível carregar config. câmeras:\n{e}")
            self.cameras = [] # Garante lista vazia

    def start_cameras(self):
        """ Tenta conectar todas as câmeras carregadas que não estão conectadas """
        try:
            self.logger.info("Iniciando conexão com câmeras carregadas...")
            connected_count = 0
            for camera in self.cameras:
                # Verifica se é um objeto Camera e se não está conectado
                if isinstance(camera, Camera) and not camera.connected:
                    if camera.connect(): # Usa o método connect do objeto Camera
                         connected_count += 1
                    else:
                         # Log mais detalhado da falha
                         self.logger.warning(f"Falha conexão automática: IP={getattr(camera, 'ip', 'N/A')}, RTSP={getattr(camera, 'rtsp_url', 'N/A')}")
                elif isinstance(camera, Camera) and camera.connected:
                     # Conta as que já estavam conectadas
                     connected_count += 1
                elif not isinstance(camera, Camera):
                     self.logger.warning(f"Item inválido encontrado na lista de câmeras ao iniciar: {type(camera)}")

            self.logger.info(f"{connected_count} de {len(self.cameras)} câmeras conectadas.")
        except Exception as e:
            self.logger.error(f"Erro ao iniciar/conectar câmeras: {e}", exc_info=True)
    # --- FIM de load_cameras e start_cameras ---

    def create_video_labels(self):
        try:
            for label in self.labels:
                if label.winfo_exists(): label.destroy()
            self.labels = []; self.aspect_ratios = []
            num_cameras = len(self.cameras); display_cells = max(num_cameras, 1)
            cols = 2; rows = (display_cells + cols - 1) // cols
            for i in range(rows): self.frame_container.grid_rowconfigure(i, weight=1)
            for i in range(cols): self.frame_container.grid_columnconfigure(i, weight=1)
            for i in range(num_cameras):
                label = tk.Label(self.frame_container, bg="black", text=f"Câmera {i+1}", fg="white")
                row = i // cols; col = i % cols
                label.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
                self.labels.append(label); self.aspect_ratios.append("fit")
                self.add_context_menu(label, i)
            self.logger.info(f"Labels criados para {num_cameras} câmeras.")
            if num_cameras == 0:
                 no_cam_label = tk.Label(self.frame_container, text="Nenhuma câmera.", bg="black", fg="white")
                 no_cam_label.grid(row=0, column=0, columnspan=cols, sticky="nsew")
        except Exception as e: self.logger.error(f"Erro criar labels: {e}", exc_info=True)

    def add_context_menu(self, label, index):
        try:
            menu = tk.Menu(label, tearoff=0)
            menu.add_command(label="4:3", command=lambda idx=index: self.set_aspect_ratio(idx, "4:3"))
            menu.add_command(label="16:9", command=lambda idx=index: self.set_aspect_ratio(idx, "16:9"))
            menu.add_command(label="Ajustar", command=lambda idx=index: self.set_aspect_ratio(idx, "fit"))
            label.bind("<Button-3>", lambda event, m=menu: m.post(event.x_root, event.y_root))
        except Exception as e: self.logger.error(f"Erro menu contexto label {index}: {e}")

    def set_aspect_ratio(self, index, ratio):
        try:
            if 0 <= index < len(self.aspect_ratios): self.aspect_ratios[index] = ratio; self.logger.info(f"Aspect ratio cam {index} -> {ratio}")
            else: self.logger.warning(f"Índice {index} inválido p/ aspect ratio.")
        except Exception as e: self.logger.error(f"Erro set aspect ratio {index}: {e}")

    def resize_frame(self, frame, label, aspect_ratio_str):
        try:
            if frame is None: return None
            label_width = label.winfo_width(); label_height = label.winfo_height()
            if label_width <= 1 or label_height <= 1: return None # Label sem tamanho ainda
            frame_height, frame_width = frame.shape[:2]
            if frame_height == 0 or frame_width == 0: return None

            target_ratio = None; interpolation = cv2.INTER_AREA
            if aspect_ratio_str == "4:3": target_ratio = 4/3
            elif aspect_ratio_str == "16:9": target_ratio = 16/9
            elif aspect_ratio_str != "fit": aspect_ratio_str = "fit"

            if aspect_ratio_str == "fit":
                if label_width > frame_width: interpolation = cv2.INTER_LINEAR
                return cv2.resize(frame, (label_width, label_height), interpolation=interpolation)

            new_width = label_width; new_height = int(new_width / target_ratio)
            if new_height > label_height: new_height = label_height; new_width = int(new_height * target_ratio)
            new_width = max(1, new_width); new_height = max(1, new_height)
            if new_width > frame_width: interpolation = cv2.INTER_LINEAR
            resized_content = cv2.resize(frame, (new_width, new_height), interpolation=interpolation)

            if new_width != label_width or new_height != label_height:
                top = (label_height - new_height)//2; left = (label_width - new_width)//2
                output_frame = np.zeros((label_height, label_width, 3), dtype=np.uint8)
                output_frame[top:top + new_height, left:left + new_width] = resized_content
                return output_frame
            else: return resized_content
        except Exception as e: self.logger.error(f"Erro resize frame: {e}", exc_info=True); return None

    def open_camera_list_window(self):
        try:
            if self.camera_list_window is not None and self.camera_list_window.winfo_exists(): self.camera_list_window.lift(); return
            self.camera_list_window = tk.Toplevel(self.root); self.camera_list_window.title("Gerenciar Câmeras")
            self.camera_list_window.geometry("800x400"); self.center_window(self.camera_list_window)
            button_frame = ttk.Frame(self.camera_list_window, padding="5"); button_frame.pack(side=tk.TOP, fill=tk.X)
            ttk.Button(button_frame, text="Ad. ONVIF", command=self.add_onvif_camera_dialog).pack(side=tk.LEFT, padx=2)
            ttk.Button(button_frame, text="Ad. RTSP", command=self.add_rtsp_camera_dialog).pack(side=tk.LEFT, padx=2)
            ttk.Button(button_frame, text="Editar", command=self.edit_camera_dialog).pack(side=tk.LEFT, padx=2)
            ttk.Button(button_frame, text="Remover", command=self.remove_camera).pack(side=tk.LEFT, padx=2)
            ttk.Button(button_frame, text="Buscar ONVIF", command=self.discover_cameras).pack(side=tk.LEFT, padx=2)
            ttk.Button(button_frame, text="Fechar", command=self.on_camera_list_window_close).pack(side=tk.RIGHT, padx=5)
            list_frame = ttk.Frame(self.camera_list_window, padding="5"); list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            cols = ("type", "ip", "port", "username", "rtsp_url", "status"); self.camera_list = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse")
            self.camera_list.heading("type", text="Tipo"); self.camera_list.column("type", width=60, anchor=tk.W)
            self.camera_list.heading("ip", text="IP"); self.camera_list.column("ip", width=120, anchor=tk.W)
            self.camera_list.heading("port", text="Porta"); self.camera_list.column("port", width=50, anchor=tk.CENTER)
            self.camera_list.heading("username", text="Usuário"); self.camera_list.column("username", width=100, anchor=tk.W)
            self.camera_list.heading("rtsp_url", text="URL RTSP"); self.camera_list.column("rtsp_url", width=300, anchor=tk.W)
            self.camera_list.heading("status", text="Status"); self.camera_list.column("status", width=100, anchor=tk.CENTER)
            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.camera_list.yview); self.camera_list.configure(yscroll=scrollbar.set)
            self.camera_list.grid(row=0, column=0, sticky="nsew"); scrollbar.grid(row=0, column=1, sticky="ns")
            list_frame.grid_rowconfigure(0, weight=1); list_frame.grid_columnconfigure(0, weight=1)
            self.populate_camera_list_view()
            self.camera_list_window.protocol("WM_DELETE_WINDOW", self.on_camera_list_window_close)
            self.logger.info("Janela gerenciamento aberta.")
        except Exception as e: self.logger.error(f"Erro abrir gerenciamento: {e}", exc_info=True)

    def populate_camera_list_view(self):
        if not (self.camera_list_window and self.camera_list_window.winfo_exists() and hasattr(self, 'camera_list') and self.camera_list): return
        try:
             for item in self.camera_list.get_children(): self.camera_list.delete(item)
             for i, cam in enumerate(self.cameras):
                 if isinstance(cam, Camera):
                      camera_type="RTSP" if cam.rtsp_url else "ONVIF"; status="Conectado" if cam.connected else "Desconectado"; tag="connected" if cam.connected else "disconnected"
                      values=(camera_type, cam.ip, str(cam.port), cam.username or "-", cam.rtsp_url or "-", status)
                      self.camera_list.insert("", tk.END, values=values, tags=(tag,))
                 else: self.logger.warning(f"Item inválido {i} ao popular lista.")
             self.camera_list.tag_configure("disconnected", foreground="red"); self.camera_list.tag_configure("connected", foreground="green")
        except Exception as e: self.logger.error(f"Erro popular lista: {e}", exc_info=True)

# Dentro da classe CameraApp em app.py
    # Substitua o método discover_cameras existente por este:

    def discover_cameras(self):
        """ Realiza a busca ONVIF (Com correção no finally e formatação) """
        wsd = None
        status_label = None
        try:
            if not (self.camera_list_window and self.camera_list_window.winfo_exists()):
                 messagebox.showerror("Erro", "Abra a janela 'Gerenciar Câmeras' primeiro.")
                 return
            # Verifica se ONVIFCamera está disponível
            if ONVIFCamera is None:
                messagebox.showerror("Erro", "Biblioteca ONVIF não carregada. Verifique a instalação de 'onvif-zeep'.")
                return

            self.logger.info("Iniciando busca automática de câmeras ONVIF...")
            status_label = ttk.Label(self.camera_list_window, text="Buscando câmeras ONVIF...")
            status_label.pack(side=tk.BOTTOM, fill=tk.X)
            self.camera_list_window.update_idletasks()

            # Limpa itens 'Descoberto' da lista
            items_to_remove = []
            if hasattr(self, 'camera_list') and self.camera_list: # Garante que camera_list existe
                for item_id in self.camera_list.get_children():
                    try:
                        values = self.camera_list.item(item_id, "values")
                        # Verifica se values não está vazio e tem o índice do status
                        if values and len(values) >= 6 and isinstance(values[5], str) and values[5].startswith("Descoberto"):
                            items_to_remove.append(item_id)
                    except IndexError:
                        self.logger.warning(f"Item {item_id} na Treeview com formato inesperado de valores.")
                for item_id in items_to_remove:
                    self.camera_list.delete(item_id)

            # --- WSDiscovery ---
            wsd = WSDiscovery()
            wsd.start()
            # Cria QName com getLocalname e getNamespacePrefix (corrigido)
            type_ = SimpleQName("http://www.onvif.org/ver10/network/wsdl", "NetworkVideoTransmitter")
            services = wsd.searchServices(types=[type_], timeout=5)
            wsd.stop() # Para logo após a busca
            # -----------------

            discovered_cameras_info = []
            existing_ips = {cam.ip for cam in self.cameras if isinstance(cam, Camera)} # IPs já configurados

            for service in services:
                ip = None
                xaddrs = service.getXAddrs()

                # Lógica de extração de IP (formatada para clareza)
                if xaddrs:
                    for xaddr in xaddrs:
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', xaddr)
                        if ip_match:
                            potential_ip = ip_match.group(1)
                            # Ignora loopback se houver outros endereços
                            if potential_ip != "127.0.0.1" or len(xaddrs) == 1:
                                ip = potential_ip
                                break # Usa o primeiro IP válido
                # Se não achou IP nos xaddrs, tenta o EPR
                if not ip:
                    try:
                        epr = service.getEPR()
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', epr)
                        if ip_match:
                            ip = ip_match.group(1)
                    except Exception:
                        pass # Ignora erros ao obter/parsear EPR

                # Pula se não conseguiu IP ou se já existe
                if not ip:
                    self.logger.warning(f"Não foi possível extrair IP do serviço descoberto: XAddrs={xaddrs}, EPR={service.getEPR()}")
                    continue
                if ip in existing_ips or ip in [info["ip"] for info in discovered_cameras_info]:
                    continue

                # Adiciona à lista de descobertos (sem conectar aqui)
                port = 80
                discovered_cameras_info.append({
                    "type": "ONVIF", "ip": ip, "port": port,
                    "username": "", "rtsp_url": "",
                    "status": "Descoberto"
                })
                self.logger.info(f"Câmera ONVIF descoberta: IP={ip}")
            # --- Fim do loop for service ---

            # Adiciona câmeras descobertas à Treeview (se existir)
            added_count = 0
            if hasattr(self, 'camera_list') and self.camera_list:
                for cam_info in discovered_cameras_info:
                    try:
                        self.camera_list.insert("", tk.END, values=(
                            cam_info["type"], cam_info["ip"], cam_info["port"],
                            cam_info["username"], cam_info["rtsp_url"], cam_info["status"]
                        ), tags=("discovered",))
                        added_count += 1
                    except Exception as insert_err:
                         self.logger.error(f"Erro ao inserir câmera descoberta {cam_info['ip']} na lista: {insert_err}")
                self.camera_list.tag_configure("discovered", foreground="blue")

            # Finaliza e informa o usuário
            if status_label and status_label.winfo_exists(): status_label.destroy()
            self.logger.info(f"Busca ONVIF concluída. {added_count} novas câmeras descobertas.")
            messagebox.showinfo("Busca Concluída", f"{added_count} novas câmeras ONVIF encontradas.", parent=self.camera_list_window)

        except Exception as e:
            if status_label and status_label.winfo_exists(): status_label.destroy()
            self.logger.error(f"Erro durante a busca: {e}", exc_info=True)
            # Mostra erro na janela pai correta
            parent_win = self.camera_list_window if (self.camera_list_window and self.camera_list_window.winfo_exists()) else self.root
            messagebox.showerror("Erro Busca", f"Erro durante a busca: {e}", parent=parent_win)
        finally:
            # Garante que wsd.stop() seja chamado sem checar _is_running
            if 'wsd' in locals() and wsd is not None:
                 try:
                      self.logger.debug("Tentando parar WSDiscovery no finally...")
                      # Verifica se o método stop existe antes de chamar
                      if hasattr(wsd, 'stop') and callable(wsd.stop):
                           wsd.stop()
                           self.logger.debug("WSDiscovery parado no finally.")
                      else:
                           self.logger.warning("Objeto WSD não possui método stop() esperado.")
                 except Exception as stop_error:
                      self.logger.warning(f"Erro (ignorado) ao parar WSDiscovery no finally: {stop_error}")

    def on_camera_list_window_close(self):
        try:
            if self.camera_list_window and self.camera_list_window.winfo_exists(): self.camera_list_window.destroy()
            self.camera_list_window = None; self.logger.info("Janela gerenciamento fechada.")
        except Exception as e: self.logger.error(f"Erro fechar gerenciamento: {e}")

    def add_onvif_camera_dialog(self):
        try:
             # Verifica se ONVIFCamera está disponível
             if ONVIFCamera is None: messagebox.showerror("Erro", "Biblioteca ONVIF não carregada."); return
             parent_window = self.camera_list_window if (self.camera_list_window and self.camera_list_window.winfo_exists()) else self.root
             dialog = tk.Toplevel(parent_window); dialog.title("Adicionar ONVIF"); dialog.geometry("300x200"); dialog.transient(parent_window); dialog.grab_set(); self.center_window(dialog)
             frame = ttk.Frame(dialog, padding="10"); frame.pack(expand=True, fill=tk.BOTH)
             ttk.Label(frame, text="IP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5); ip_entry = ttk.Entry(frame, width=25); ip_entry.grid(row=0, column=1, padx=5, pady=5)
             ttk.Label(frame, text="Porta:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5); port_entry = ttk.Entry(frame, width=10); port_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W); port_entry.insert(0, "80")
             ttk.Label(frame, text="Usuário:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5); user_entry = ttk.Entry(frame, width=25); user_entry.grid(row=2, column=1, padx=5, pady=5)
             ttk.Label(frame, text="Senha:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5); password_entry = ttk.Entry(frame, width=25, show="*"); password_entry.grid(row=3, column=1, padx=5, pady=5)

             def save_camera():
                 ip=ip_entry.get().strip(); port_str=port_entry.get().strip(); username=user_entry.get().strip(); password=password_entry.get()
                 if not ip or not port_str or not username: messagebox.showerror("Erro", "IP, Porta, Usuário obrigatórios.", parent=dialog); return
                 try: port = int(port_str)
                 except ValueError: messagebox.showerror("Erro", "Porta inválida.", parent=dialog); return
                 camera = Camera(ip, port, username, password, logger=self.logger)
                 if camera.connect(timeout=10):
                     self.cameras.append(camera); self.populate_camera_list_view(); save_cameras(self.cameras, self.logger); self.create_video_labels(); dialog.destroy(); self.logger.info(f"ONVIF adicionada: {ip}")
                 else: messagebox.showerror("Erro", f"Falha conexão ONVIF {ip}.", parent=dialog)

             bf = ttk.Frame(dialog); bf.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10); ttk.Button(bf, text="Salvar", command=save_camera).pack(side=tk.RIGHT, padx=5); ttk.Button(bf, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT)
             dialog.bind("<Return>", lambda e: save_camera()); dialog.bind("<Escape>", lambda e: dialog.destroy()); ip_entry.focus_set(); self.logger.info("Diálogo ONVIF aberto.")
        except Exception as e: self.logger.error(f"Erro diálogo ONVIF: {e}", exc_info=True); messagebox.showerror("Erro", f"Erro diálogo ONVIF:\n{e}")

    def add_rtsp_camera_dialog(self):
        try:
            parent_window = self.camera_list_window if (self.camera_list_window and self.camera_list_window.winfo_exists()) else self.root
            dialog = tk.Toplevel(parent_window); dialog.title("Adicionar RTSP"); dialog.geometry("450x150"); dialog.transient(parent_window); dialog.grab_set(); self.center_window(dialog)
            frame = ttk.Frame(dialog, padding="10"); frame.pack(expand=True, fill=tk.BOTH)
            ttk.Label(frame, text="URL RTSP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5); rtsp_entry = ttk.Entry(frame, width=50); rtsp_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew"); frame.grid_columnconfigure(1, weight=1)
            ttk.Label(frame, text="Ex: rtsp://user:pass@ip:port/stream").grid(row=1, column=1, sticky=tk.W, padx=5)

            def save_camera():
                rtsp_url=rtsp_entry.get().strip();
                if not rtsp_url.lower().startswith("rtsp://"): messagebox.showerror("Erro", "URL RTSP inválida.", parent=dialog); return
                ip, port, user, password = "N/A", 554, "", ""
                try: match = re.match(r"rtsp://(?:([^:]+)(?::([^@]+))?@)?([^:/]+)(?::(\d+))?(?:/.*)?", rtsp_url);
                except Exception as e: messagebox.showerror("Erro", f"Análise URL falhou:\n{e}", parent=dialog); return
                if match: user, password, ip, port_str = match.groups(); user = user or ""; password = password or ""; port = int(port_str or 554)
                else: messagebox.showerror("Erro", "Formato URL não reconhecido.", parent=dialog); return

                camera = Camera(ip, port, user, password, rtsp_url, logger=self.logger)
                if camera.connect():
                    self.cameras.append(camera); self.populate_camera_list_view(); save_cameras(self.cameras, self.logger); self.create_video_labels(); dialog.destroy(); self.logger.info(f"RTSP adicionada: {rtsp_url}")
                else: messagebox.showerror("Erro", f"Falha conexão RTSP:\n{rtsp_url}", parent=dialog)

            bf = ttk.Frame(dialog); bf.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10); ttk.Button(bf, text="Salvar", command=save_camera).pack(side=tk.RIGHT, padx=5); ttk.Button(bf, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT)
            dialog.bind("<Return>", lambda e: save_camera()); dialog.bind("<Escape>", lambda e: dialog.destroy()); rtsp_entry.focus_set(); self.logger.info("Diálogo RTSP aberto.")
        except Exception as e: self.logger.error(f"Erro diálogo RTSP: {e}", exc_info=True); messagebox.showerror("Erro", f"Erro diálogo RTSP:\n{e}")

    def edit_camera_dialog(self):
        try:
            if not (self.camera_list_window and self.camera_list_window.winfo_exists() and self.camera_list): messagebox.showerror("Erro", "Janela gerenciamento fechada."); return
            selected_items=self.camera_list.selection();
            if not selected_items: messagebox.showwarning("Aviso", "Selecione uma câmera.", parent=self.camera_list_window); return
            item_id=selected_items[0]
            try: index=self.camera_list.index(item_id); camera_to_edit=self.cameras[index]
            except Exception as e: messagebox.showerror("Erro", f"Erro achar câmera: {e}", parent=self.camera_list_window); return

            camera_type="RTSP" if camera_to_edit.rtsp_url else "ONVIF"; parent_window=self.camera_list_window
            dialog=tk.Toplevel(parent_window); dialog.title(f"Editar ({camera_type})"); dialog.transient(parent_window); dialog.grab_set()
            frame=ttk.Frame(dialog, padding="10"); frame.pack(expand=True, fill=tk.BOTH)

            if camera_type == "ONVIF":
                # Verifica se ONVIFCamera está disponível
                if ONVIFCamera is None: messagebox.showerror("Erro", "Biblioteca ONVIF não carregada."); dialog.destroy(); return
                dialog.geometry("300x200")
                ttk.Label(frame, text="IP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5); ip_entry=ttk.Entry(frame, width=25); ip_entry.grid(row=0, column=1, padx=5, pady=5); ip_entry.insert(0, camera_to_edit.ip)
                ttk.Label(frame, text="Porta:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5); port_entry=ttk.Entry(frame, width=10); port_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W); port_entry.insert(0, str(camera_to_edit.port))
                ttk.Label(frame, text="Usuário:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5); user_entry=ttk.Entry(frame, width=25); user_entry.grid(row=2, column=1, padx=5, pady=5); user_entry.insert(0, camera_to_edit.username)
                ttk.Label(frame, text="Senha:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5); password_entry=ttk.Entry(frame, width=25, show="*"); password_entry.grid(row=3, column=1, padx=5, pady=5); password_entry.insert(0, camera_to_edit.password)
            else: # RTSP
                dialog.geometry("450x150")
                ttk.Label(frame, text="URL RTSP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5); rtsp_entry=ttk.Entry(frame, width=50); rtsp_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew"); rtsp_entry.insert(0, camera_to_edit.rtsp_url); frame.grid_columnconfigure(1, weight=1)
                ttk.Label(frame, text="Ex: rtsp://user:pass@ip:port/stream").grid(row=1, column=1, sticky=tk.W, padx=5)

            def save_edited_camera():
                camera_to_edit.disconnect()
                if camera_type=="ONVIF":
                    ip=ip_entry.get().strip(); port_str=port_entry.get().strip(); username=user_entry.get().strip(); password=password_entry.get()
                    if not ip or not port_str or not username: messagebox.showerror("Erro", "IP, Porta, Usuário obrigatórios.", parent=dialog); return
                    try: port=int(port_str)
                    except ValueError: messagebox.showerror("Erro", "Porta inválida.", parent=dialog); return
                    camera_to_edit.ip=ip; camera_to_edit.port=port; camera_to_edit.username=username; camera_to_edit.password=password; camera_to_edit.rtsp_url=""
                    if camera_to_edit.connect(timeout=10): status="Conectado"; display_rtsp=camera_to_edit.rtsp_url or "-"; self.camera_list.item(item_id, values=("ONVIF", ip, port, username, display_rtsp, status)); save_cameras(self.cameras, self.logger); self.create_video_labels(); dialog.destroy(); self.logger.info(f"ONVIF editada: {ip}")
                    else: self.camera_list.item(item_id, values=("ONVIF", ip, port, username, "-", "Desconectado")); messagebox.showerror("Erro", f"Falha reconectar ONVIF {ip}.", parent=dialog)
                else: # RTSP
                    rtsp_url=rtsp_entry.get().strip()
                    if not rtsp_url.lower().startswith("rtsp://"): messagebox.showerror("Erro", "URL RTSP inválida.", parent=dialog); return
                    ip, port, user, password = "N/A", 554, "", ""
                    try: match = re.match(r"rtsp://(?:([^:]+)(?::([^@]+))?@)?([^:/]+)(?::(\d+))?(?:/.*)?", rtsp_url);
                    except Exception as e: messagebox.showerror("Erro", f"Análise URL falhou:\n{e}", parent=dialog); return
                    if match: user, password, ip, port_str = match.groups(); user=user or ""; password=password or ""; port=int(port_str or 554)
                    else: messagebox.showerror("Erro", "Formato URL não reconhecido.", parent=dialog); return
                    camera_to_edit.ip=ip; camera_to_edit.port=port; camera_to_edit.username=user; camera_to_edit.password=password; camera_to_edit.rtsp_url=rtsp_url
                    if camera_to_edit.connect(): self.camera_list.item(item_id, values=("RTSP", ip, port, user, rtsp_url, "Conectado")); save_cameras(self.cameras, self.logger); self.create_video_labels(); dialog.destroy(); self.logger.info(f"RTSP editada: {rtsp_url}")
                    else: self.camera_list.item(item_id, values=("RTSP", ip, port, user, rtsp_url, "Desconectado")); messagebox.showerror("Erro", f"Falha reconectar RTSP:\n{rtsp_url}", parent=dialog)

            bf = ttk.Frame(dialog); bf.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10); ttk.Button(bf, text="Salvar", command=save_edited_camera).pack(side=tk.RIGHT, padx=5); ttk.Button(bf, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT)
            dialog.bind("<Return>", lambda e: save_edited_camera()); dialog.bind("<Escape>", lambda e: dialog.destroy())
            if camera_type=="ONVIF": ip_entry.focus_set();
            else: rtsp_entry.focus_set()
            self.logger.info(f"Diálogo edição aberto p/ cam {index}")
        except Exception as e: self.logger.error(f"Erro diálogo edição: {e}", exc_info=True); messagebox.showerror("Erro", f"Erro diálogo edição:\n{e}")

    def remove_camera(self):
        try:
            if not (self.camera_list_window and self.camera_list_window.winfo_exists() and self.camera_list): messagebox.showerror("Erro", "Janela gerenciamento fechada."); return
            selected_items = self.camera_list.selection();
            if not selected_items: messagebox.showwarning("Aviso", "Selecione uma câmera.", parent=self.camera_list_window); return
            item_id = selected_items[0]
            try: index = self.camera_list.index(item_id); camera_to_remove = self.cameras[index]
            except Exception as e: messagebox.showerror("Erro", f"Erro achar câmera: {e}", parent=self.camera_list_window); return

            if messagebox.askyesno("Confirmar Remoção", f"Remover câmera {getattr(camera_to_remove, 'ip', 'Desconhecida')}?", parent=self.camera_list_window):
                if isinstance(camera_to_remove, Camera): camera_to_remove.disconnect()
                else: self.logger.warning(f"Removendo objeto inválido {type(camera_to_remove)} no índice {index}")
                del self.cameras[index]
                self.camera_list.delete(item_id)
                save_cameras(self.cameras, self.logger) # <<< SALVA JSON
                self.create_video_labels() # <<< RECRIA LABELS
                self.logger.info(f"Câmera índice {index} removida.")
        except Exception as e: self.logger.error(f"Erro ao remover câmera: {e}", exc_info=True); messagebox.showerror("Erro", f"Erro ao remover:\n{e}", parent=self.camera_list_window)

    def minimize_window(self):
        try: self.root.iconify(); self.logger.info("Janela minimizada.")
        except Exception as e: self.logger.error(f"Erro minimizar: {e}")

    def close_window(self):
        try:
            self.logger.info("Fechando aplicativo...")
            self.running = False
            self.logger.info("Desconectando câmeras...")
            for i, cam in enumerate(self.cameras):
                if isinstance(cam, Camera):
                    try: cam.disconnect()
                    except Exception as e: self.logger.error(f"Erro desconectar cam {i}: {e}")
                else: self.logger.warning(f"Ignorando item inválido {i} ao desconectar.")
            if self.camera_list_window and self.camera_list_window.winfo_exists():
                 try: self.camera_list_window.destroy()
                 except Exception: pass
            if self.root and self.root.winfo_exists(): self.root.destroy()
            self.logger.info("Aplicativo fechado.")
        except Exception as e: self.logger.error(f"Erro crítico fechar app: {e}", exc_info=True)

    def update_frames(self):
        try:
            if not self.running: return
            num_labels=len(self.labels); num_cameras=len(self.cameras)
            if num_labels != num_cameras: self.logger.warning(f"Labels({num_labels})!=Câmeras({num_cameras}). Recriando."); self.create_video_labels(); self.root.after(FRAME_UPDATE_INTERVAL, self.update_frames); return

            for i in range(num_cameras):
                camera=self.cameras[i]; label=self.labels[i]
                if not label.winfo_exists(): continue
                if not isinstance(camera, Camera): logger.error(f"Obj inválido {i}: {type(camera)}"); label.config(image="", text=f"Erro Obj {i}", fg="red"); continue

                frame=None;
                if camera.connected: frame=camera.get_frame()

                if frame is not None:
                    aspect=self.aspect_ratios[i] if 0 <= i < len(self.aspect_ratios) else "fit"
                    resized_frame=self.resize_frame(frame, label, aspect)
                    if resized_frame is not None:
                        try: img=Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)); imgtk=ImageTk.PhotoImage(image=img); label.config(image=imgtk, text=""); label.image=imgtk
                        except Exception as e: logger.error(f"Erro cvt/show {camera.ip}: {e}"); label.config(image="", text="Erro Exib", fg="red")
                    else: label.config(image="", text="Erro Resize", fg="red")
                else:
                    if camera.connected: logger.warning(f"Cam {camera.ip} parou frames."); camera.connected=False
                    if label.cget("text") != "Desconectado": label.config(image="", text="Desconectado", fg="orange")
                    # Atualiza status na lista SÓ se mudou para desconectado
                    if camera.connected is False: self._update_camera_list_status(i, "Desconectado")

            if self.running: self.root.after(FRAME_UPDATE_INTERVAL, self.update_frames)
        except Exception as e:
            self.logger.error(f"Erro loop update: {e}", exc_info=True)
            # Aumenta intervalo após erro para evitar spamming de logs/erros
            if self.running: self.root.after(FRAME_UPDATE_INTERVAL * 10, self.update_frames)

    def _update_camera_list_status(self, index, status_text):
        if self.camera_list_window and self.camera_list_window.winfo_exists() and hasattr(self, 'camera_list') and self.camera_list:
            try:
                children=self.camera_list.get_children()
                if 0 <= index < len(children):
                    item_id=children[index]; col_idx=5; # Status é a 6a coluna (índice 5)
                    current_values=list(self.camera_list.item(item_id)["values"])
                    # Garante que a lista tem tamanho suficiente
                    while len(current_values) <= col_idx: current_values.append("")
                    # Atualiza só se diferente
                    if current_values[col_idx] != status_text:
                        current_values[col_idx]=status_text; self.camera_list.item(item_id, values=tuple(current_values))
            except tk.TclError: pass # Ignora erro se janela/widget sumiu
            except Exception as e: self.logger.error(f"Erro update status lista: {e}", exc_info=True)

# Fim da classe CameraApp