# app.py (Layout com Place, usa utils para save/load)

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import re
import numpy as np
import cv2
import sys # Para fallback de config
# Importa PIL para exibir frames no Tkinter
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None; ImageTk = None
    print("ERRO CRÍTICO: Biblioteca Pillow (PIL) não encontrada. Instale com: pip install pillow", file=sys.stderr)
    sys.exit(1)

# Importa Camera e as funções de utils
try:
    from camera import Camera
    from utils import save_cameras, load_cameras, setup_logging, center_window
except ImportError as e:
     print(f"ERRO CRÍTICO: Falha ao importar camera.py ou utils.py: {e}", file=sys.stderr)
     # Tenta mostrar erro via Tkinter se possível
     try:
         root_err = tk.Tk(); root_err.withdraw()
         tk.messagebox.showerror("Erro de Importação", f"Não foi possível carregar módulos essenciais (camera.py ou utils.py).\nVerifique o console.\nErro: {e}")
         root_err.destroy()
     except Exception: pass
     sys.exit(1)

# Importa de config (com fallback)
try:
    from config import (FRAME_UPDATE_INTERVAL, APP_NAME, CAMERAS_JSON,
                        ONVIF_DISCOVERY_TIMEOUT, DEFAULT_ASPECT_RATIO, LOGGER_NAME)
except ImportError:
    FRAME_UPDATE_INTERVAL = 30; APP_NAME = "CameraApp_Fallback"; logger_name = APP_NAME
    CAMERAS_JSON = "cameras.json"; ONVIF_DISCOVERY_TIMEOUT = 5; DEFAULT_ASPECT_RATIO = "fit"
    print("AVISO: Não foi possível importar de config.py. Usando valores padrão.", file=sys.stderr)
    LOGGER_NAME = logger_name # Garante que LOGGER_NAME existe

# Importa libs ONVIF/Discovery com tratamento de erro
try:
    from wsdiscovery import WSDiscovery
except ImportError:
    WSDiscovery = None
    print("AVISO: Biblioteca 'WSDiscovery' não encontrada. Busca ONVIF desabilitada.", file=sys.stderr)

try:
    from onvif import ONVIFCamera
except ImportError:
    ONVIFCamera = None
    # Aviso já dado em camera.py

import logging
import threading

# Usa o logger configurado em main.py (ou utils.setup_logging)
logger = logging.getLogger(LOGGER_NAME)

# Classe QName (necessária para WSDiscovery - CORRIGIDA)
class SimpleQName:
    def __init__(self, namespace, local_part): self.namespace = namespace; self.local_part = local_part
    def getNamespace(self): return self.namespace
    def getLocalname(self): return self.local_part
    def getNamespacePrefix(self): return None
    def getFullname(self): return f"{{{self.namespace}}}{self.local_part}"
    # Adiciona __str__ e __repr__ para melhor representação
    def __str__(self): return self.getFullname()
    def __repr__(self): return f'SimpleQName({self.namespace!r}, {self.local_part!r})'

# Tenta importar QName real do Zeep como preferência
try: from zeep.xsd.types.simple import QName as ZeepQName
except ImportError: ZeepQName = SimpleQName # Usa a nossa se Zeep não tiver


# --- Classe Principal da Aplicação ---
class CameraApp:
    def __init__(self, root, logger_instance: logging.Logger):
        self.logger = logger_instance
        self.logger.info("Inicializando CameraApp...")
        self.root = root
        self.root.title(f"{APP_NAME} by CFA TECH")
        self.root.attributes("-fullscreen", True) # Força tela cheia
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)
        self.cameras: list[Camera] = []
        self.labels = []
        self.aspect_ratios = [] # Lista para guardar aspect ratio de cada label
        self.camera_list_window = None # Janela Toplevel para a lista
        self._after_id_update = None # Guarda ID da chamada 'after'
        self.running = True

        style = ttk.Style()
        try: style.theme_use("clam")
        except tk.TclError: pass

        self.create_menu()
        self.create_widgets()
        self.logger.info("CameraApp inicializado.")

    def create_menu(self):
        """Cria a barra de menu principal."""
        try:
            menubar = tk.Menu(self.root)
            self.root.config(menu=menubar)
            opcoes_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Opções", menu=opcoes_menu)
            # Simplificado: Gerenciar abre a janela com todas as opções
            opcoes_menu.add_command(label="Gerenciar Câmeras", command=self.open_camera_list_window)
            opcoes_menu.add_separator()
            opcoes_menu.add_command(label="Minimizar", command=self.minimize_window)
            opcoes_menu.add_command(label="Sair", command=self.close_window)
            self.logger.info("Menu criado.")
        except Exception as e:
            self.logger.error(f"Erro ao criar menu: {e}", exc_info=True)

    def create_widgets(self):
        """Cria os widgets principais da interface."""
        try:
            # Frame para botões Minimizar/Fechar
            button_frame = ttk.Frame(self.root, padding="2")
            button_frame.pack(side=tk.TOP, fill=tk.X)
            # Botões alinhados à direita
            close_button = ttk.Button(button_frame, text="Fechar", command=self.close_window)
            close_button.pack(side=tk.RIGHT, padx=5)
            minimize_button = ttk.Button(button_frame, text="Minimizar", command=self.minimize_window)
            minimize_button.pack(side=tk.RIGHT, padx=5)

            # Frame container para os vídeos
            self.frame_container = tk.Frame(self.root, bg="black")
            self.frame_container.pack(expand=True, fill=tk.BOTH)

            # Sequência: Carrega -> Cria Labels -> Inicia Conexões -> Inicia Update Loop
            self.load_cameras()
            self.create_video_labels()
            self.start_cameras()
            self.update_frames() # Chama a primeira vez
            self.logger.info("Widgets criados e câmeras iniciadas.")
        except Exception as e:
            self.logger.critical(f"Erro fatal ao criar widgets: {e}", exc_info=True)
            messagebox.showerror("Erro Crítico", f"Falha ao criar interface:\n{e}")
            self.close_window()

    def load_cameras(self):
        """ Carrega câmeras do arquivo JSON usando a função de utils.py """
        self.logger.info(f"Carregando câmeras de {CAMERAS_JSON}...")
        # Chama load_cameras de utils, passando o logger
        self.cameras = load_cameras(self.logger) # Atribui a self.cameras
        self.logger.info(f"{len(self.cameras)} câmeras carregadas.")

    def save_app_cameras(self):
        """ Salva a lista atual de câmeras usando a função de utils.py """
        # Chama save_cameras de utils, passando a lista e o logger
        if not save_cameras(self.cameras, CAMERAS_JSON, self.logger):
             messagebox.showerror("Erro", "Falha ao salvar configurações das câmeras.")

    def start_cameras(self):
        """ Tenta conectar todas as câmeras carregadas."""
        try:
            self.logger.info("Iniciando conexão com câmeras carregadas...")
            connected_count = 0
            threads = []
            # Conecta em threads separadas para não bloquear a UI durante a conexão inicial
            def connect_cam(cam):
                 nonlocal connected_count
                 if cam.connect():
                     # Usa lock se precisar modificar connected_count de forma thread-safe
                     # com lock: connected_count += 1
                      self.logger.info(f"Conexão inicial para {cam.ip} OK.")
                 else:
                      self.logger.warning(f"Falha na conexão inicial: IP={getattr(cam, 'ip', 'N/A')}")

            for camera in self.cameras:
                if isinstance(camera, Camera) and not camera.connected:
                    t = threading.Thread(target=connect_cam, args=(camera,), daemon=True)
                    threads.append(t)
                    t.start()
                elif isinstance(camera, Camera) and camera.connected:
                     # Já estava conectada? (improvável após load, mas seguro verificar)
                     connected_count += 1
                else:
                     self.logger.warning(f"Item inválido encontrado ao iniciar: {type(camera)}")

            # Espera um tempo limitado pelas threads de conexão inicial (opcional)
            # timeout_join = 15 # Espera até 15s
            # for t in threads:
            #      t.join(timeout=timeout_join/len(threads) if threads else timeout_join)

            # O status real será atualizado no update_frames
            self.logger.info(f"Tentativas de conexão inicial disparadas para {len(threads)} câmeras.")

        except Exception as e:
            self.logger.error(f"Erro ao iniciar/conectar câmeras: {e}", exc_info=True)

    # --- Layout e Atualização dos Vídeos ---
    def create_video_labels(self):
        """Cria/recria os labels para exibir os vídeos usando place."""
        self.logger.debug("Recriando labels de vídeo...")
        for label in self.labels:
            try:
                if label.winfo_exists(): label.destroy()
            except tk.TclError: pass # Ignora erro se já destruído
        self.labels = []
        self.aspect_ratios = []

        num_cameras = len(self.cameras)
        num_cells = max(num_cameras, 1) # Pelo menos 1 célula
        self.logger.debug(f"Número de câmeras para exibir labels: {num_cameras}")

        # Layout dinâmico
        if num_cells <= 1: cols = 1
        elif num_cells <= 2: cols = 2
        elif num_cells <= 4: cols = 2
        elif num_cells <= 6: cols = 3
        elif num_cells <= 9: cols = 3
        elif num_cells <= 12: cols = 4
        elif num_cells <= 16: cols = 4
        else: cols = 5
        rows = (num_cells + cols - 1) // cols
        self.logger.debug(f"Layout: {rows} linhas x {cols} colunas")

        # Garante que o frame container existe e está visível
        if not self.frame_container or not self.frame_container.winfo_exists():
            self.logger.error("frame_container não existe ao criar labels.")
            return
        self.frame_container.update_idletasks()

        # Cria labels para as câmeras existentes
        for i in range(num_cameras):
            label = tk.Label(self.frame_container, bg="black", text=f"Câmera {i+1}", fg="gray")
            self.labels.append(label)
            self.aspect_ratios.append(DEFAULT_ASPECT_RATIO)

            row_num = i // cols; col_num = i % cols
            rel_width = 1.0 / cols; rel_height = 1.0 / rows

            label.place(relx=col_num*rel_width, rely=row_num*rel_height, relwidth=rel_width, relheight=rel_height)
            self.add_context_menu(label, i)

        # Preenche células restantes com labels vazios
        for i in range(num_cameras, num_cells):
             label = tk.Label(self.frame_container, bg="black")
             row_num = i // cols; col_num = i % cols
             rel_width = 1.0 / cols; rel_height = 1.0 / rows
             label.place(relx=col_num*rel_width, rely=row_num*rel_height, relwidth=rel_width, relheight=rel_height)
             # Guarda referência para limpeza posterior (opcional, mas mais limpo)
             self.labels.append(label) # Adiciona placeholders à lista também

        # Mensagem se não houver câmeras
        if num_cameras == 0:
            self.labels[0].config(text="Nenhuma câmera configurada.\nUse Opções > Gerenciar Câmeras.", fg="white", justify=tk.CENTER)

        self.logger.info(f"{len(self.labels)} labels de vídeo criados/atualizados para {num_cameras} câmeras em {num_cells} células.")


    def add_context_menu(self, label, index):
        """Adiciona menu de contexto para aspect ratio."""
        # Verifica se o índice é válido para aspect_ratios
        if not (0 <= index < len(self.aspect_ratios)): return
        try:
            menu = tk.Menu(label, tearoff=0)
            menu.add_command(label="Ajustar", command=lambda idx=index: self.set_aspect_ratio(idx, "fit"))
            menu.add_command(label="4:3", command=lambda idx=index: self.set_aspect_ratio(idx, "4:3"))
            menu.add_command(label="16:9", command=lambda idx=index: self.set_aspect_ratio(idx, "16:9"))
            # Usa lambda para capturar o menu correto
            label.bind("<Button-3>", lambda event, m=menu: m.post(event.x_root, event.y_root))
        except Exception as e: self.logger.error(f"Erro menu contexto label {index}: {e}")

    def set_aspect_ratio(self, index, ratio):
        """Define o aspect ratio para uma câmera/label."""
        try:
            if 0 <= index < len(self.aspect_ratios):
                self.aspect_ratios[index] = ratio
                self.logger.info(f"Aspect ratio cam {index} -> {ratio}")
                # Força redesenho do frame específico (opcional, pode esperar próximo update)
                # self._update_single_frame(index)
            else: self.logger.warning(f"Índice {index} inválido p/ aspect ratio.")
        except Exception as e: self.logger.error(f"Erro set aspect ratio {index}: {e}")

    def resize_frame(self, frame, label, aspect_ratio_str):
        """Redimensiona o frame para caber no label, mantendo aspect ratio se especificado."""
        try:
            if frame is None: return None
            # Tenta obter tamanho do label, usa fallback se falhar
            try:
                 label_width = label.winfo_width(); label_height = label.winfo_height()
                 if label_width <= 1 or label_height <= 1: raise ValueError("Label sem tamanho")
            except Exception: # Captura TclError também se janela fechada
                 # Fallback usando tamanho do container e layout
                 try:
                      container_w = self.frame_container.winfo_width(); container_h = self.frame_container.winfo_height()
                      num_cells = max(len(self.cameras), 1); cols = 2; rows = (num_cells + cols - 1) // cols
                      if container_w > 1 and container_h > 1 and cols > 0 and rows > 0:
                           label_width = container_w // cols; label_height = container_h // rows
                      else: label_width, label_height = 320, 240 # Ultimo recurso
                 except Exception: label_width, label_height = 320, 240
                 self.logger.debug(f"Label sem tamanho, usando fallback {label_width}x{label_height}")

            frame_height, frame_width = frame.shape[:2]
            if frame_height == 0 or frame_width == 0: return None

            target_ratio = None; interpolation = cv2.INTER_AREA
            if aspect_ratio_str == "4:3": target_ratio = 4/3
            elif aspect_ratio_str == "16:9": target_ratio = 16/9
            elif aspect_ratio_str != "fit": aspect_ratio_str = "fit"

            if aspect_ratio_str == "fit":
                if label_width > frame_width or label_height > frame_height: interpolation = cv2.INTER_LINEAR
                # Verifica se o tamanho de destino é válido
                if label_width > 0 and label_height > 0:
                    return cv2.resize(frame, (label_width, label_height), interpolation=interpolation)
                else: return None # Não redimensiona se tamanho inválido
            else: # Manter aspect ratio (letterbox/pillarbox)
                # Calcula a escala para caber no label mantendo o aspect ratio original do *frame*
                scale = min(label_width / frame_width, label_height / frame_height)
                new_width = int(frame_width * scale); new_height = int(frame_height * scale)
                new_width = max(1, new_width); new_height = max(1, new_height)

                if new_width > frame_width or new_height > frame_height: interpolation = cv2.INTER_LINEAR
                if new_width > 0 and new_height > 0:
                     resized_content = cv2.resize(frame, (new_width, new_height), interpolation=interpolation)
                else: return None # Não redimensiona se tamanho inválido

                # Cria fundo preto e centraliza
                output_frame = np.zeros((label_height, label_width, 3), dtype=np.uint8)
                top = (label_height - new_height) // 2
                left = (label_width - new_width) // 2
                # Verifica limites antes de copiar
                if top >= 0 and left >= 0 and top + new_height <= label_height and left + new_width <= label_width:
                    output_frame[top:top + new_height, left:left + new_width] = resized_content
                    return output_frame
                else:
                     self.logger.warning("Erro de cálculo ao centralizar frame redimensionado.")
                     # Retorna o frame redimensionado sem centralizar como fallback
                     # Ou um frame vazio se preferir
                     if resized_content.shape[0] <= label_height and resized_content.shape[1] <= label_width:
                         output_frame[:new_height, :new_width] = resized_content
                         return output_frame
                     else: return None


        except Exception as e:
            self.logger.error(f"Erro no resize_frame: {e}", exc_info=True)
            return None

    def update_frames(self):
        """Atualiza os frames de vídeo nos labels (loop principal da UI)."""
        try:
            if not self.running: return

            # Verifica se precisa recriar labels (número mudou)
            # Compara número de câmeras com número de labels *reais* (exclui placeholders se necessário)
            # Simplificação: sempre recria se len(self.labels) != max(len(self.cameras), 1) ? Não, usa len(self.cameras)
            num_cameras = len(self.cameras)
            num_labels = len(self.labels)

            # Se temos labels mas não temos câmeras (depois de remover a última)
            if num_cameras == 0 and num_labels > 0:
                 if not self.labels[0].cget("text").startswith("Nenhuma câmera"):
                     self.create_video_labels() # Recria para mostrar msg

            # Se o número de labels (excluindo placeholders se houver) não bate com câmeras
            elif num_labels != num_cameras and num_cameras > 0 :
                 self.logger.warning(f"Inconsistência: Labels({num_labels}) != Câmeras({num_cameras}). Recriando labels.")
                 self.create_video_labels()
                 # Reagenda e sai para evitar erros de índice nesta iteração
                 if self.running: self._after_id_update = self.root.after(FRAME_UPDATE_INTERVAL, self.update_frames)
                 return

            # Itera sobre o número de câmeras (que deve bater com labels agora)
            for i in range(num_cameras):
                if i >= len(self.labels): break # Segurança extra

                camera = self.cameras[i]
                label = self.labels[i]

                if not label.winfo_exists(): continue
                if not isinstance(camera, Camera): logger.error(f"Obj inválido {i}: {type(camera)}"); label.config(image="", text=f"Erro Obj {i}", fg="red"); continue

                frame = camera.get_frame() # Pega da fila (não bloqueante)
                status_changed = False

                if frame is not None:
                    aspect = self.aspect_ratios[i] if 0 <= i < len(self.aspect_ratios) else DEFAULT_ASPECT_RATIO
                    resized_frame = self.resize_frame(frame, label, aspect)
                    if resized_frame is not None:
                        try:
                            img = Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB))
                            imgtk = ImageTk.PhotoImage(image=img)
                            label.config(image=imgtk, text="") # Limpa texto
                            label.image = imgtk # Guarda referência
                            if not camera.connected: # Se estava desconectado e recebeu frame
                                self.logger.info(f"Câmera {camera.ip} reconectada (frame recebido).")
                                camera.connected = True; status_changed = True
                        except Exception as e:
                            self.logger.error(f"Erro ao converter/exibir frame de {camera.ip}: {e}")
                            label.config(image="", text="Erro Exib.", fg="red")
                            if camera.connected: camera.connected = False; status_changed = True
                    else: # Erro no resize
                        label.config(image="", text="Erro Resize", fg="red")
                        if camera.connected: camera.connected = False; status_changed = True
                else: # Nenhum frame recebido da fila
                    if camera.connected:
                         # Thread está rodando mas fila vazia? Pode ser lag ou início de desconexão.
                         # Não marca como desconectado ainda, a thread interna fará isso.
                         current_text = label.cget("text")
                         if not current_text.startswith("Sem Sinal"): label.config(image="", text="Sem Sinal...", fg="orange"); label.image=None
                    else:
                         # Já está desconectado (confirmado pela thread/connect)
                         current_text = label.cget("text")
                         if current_text != "Desconectado": label.config(image="", text="Desconectado", fg="red"); label.image=None; status_changed=True

                # Atualiza status na TreeView SÓ SE MUDOU e a janela estiver aberta
                if status_changed:
                    new_status_text = "Conectado" if camera.connected else "Desconectado"
                    self._update_camera_list_status(i, new_status_text)

            # Agenda a próxima atualização
            if self.running:
                self._after_id_update = self.root.after(FRAME_UPDATE_INTERVAL, self.update_frames)

        except Exception as e:
            self.logger.error(f"Erro no loop principal update_frames: {e}", exc_info=True)
            # Tenta reagendar com delay maior
            if self.running:
                try: self._after_id_update = self.root.after(FRAME_UPDATE_INTERVAL * 10, self.update_frames)
                except tk.TclError: pass # Ignora erro se root já foi destruído

    def _update_camera_list_status(self, index, status_text):
        """Atualiza a coluna 'Status' na Treeview."""
        if self.camera_list_window and self.camera_list_window.winfo_exists():
            treeview = self.get_treeview_from_toplevel(self.camera_list_window)
            if treeview:
                try:
                    children = treeview.get_children()
                    if 0 <= index < len(children):
                        item_id = children[index]
                        # A coluna 'status' é a 6a (índice 5)
                        col_idx = 5
                        current_values = list(treeview.item(item_id, "values"))
                        # Verifica tamanho da lista antes de acessar
                        if len(current_values) > col_idx:
                            if current_values[col_idx] != status_text:
                                current_values[col_idx] = status_text
                                treeview.item(item_id, values=tuple(current_values))
                                tag = "connected" if status_text == "Conectado" else "disconnected"
                                treeview.item(item_id, tags=(tag,)) # Aplica tag para cor
                                self.logger.debug(f"Status da câmera {index} atualizado para '{status_text}' na lista.")
                        else:
                             self.logger.warning(f"Formato inesperado de 'values' para item {item_id} ao atualizar status.")

                except tk.TclError: pass # Janela pode ter sido fechada
                except Exception as e: self.logger.error(f"Erro ao atualizar status da lista {index}: {e}", exc_info=True)

    # --- Janela de Gerenciamento de Câmeras ---
    # Mantém os métodos open_camera_list_window, populate_camera_list_view,
    # on_camera_list_window_close, add_onvif_camera_dialog, add_rtsp_camera_dialog,
    # edit_camera_dialog, remove_camera, discover_cameras como definidos no seu app.txt
    # (Já pareciam corretos e lidavam com a janela Toplevel)
    # Apenas garantir que save_cameras agora chama self.save_app_cameras()

    # CORREÇÃO DENTRO DOS MÉTODOS DE DIÁLOGO:
    # Onde você tinha save_cameras(self.cameras, self.logger), mude para self.save_app_cameras()
    # Exemplo dentro de add_onvif_camera_dialog -> save_camera:
    #     ...
    #     if new_camera.connect():
    #          self.cameras.append(new_camera)
    #          self.save_app_cameras() # <<< CHAMA O MÉTODO DA CLASSE
    #          self.populate_camera_list_view()
    #          self.create_video_labels()
    #          dialog.destroy()
    #     ...
    # FAÇA O MESMO EM add_rtsp_camera_dialog -> save_camera
    # FAÇA O MESMO EM edit_camera_dialog -> save_edited_camera
    # FAÇA O MESMO EM remove_camera (já estava certo no seu código)


    # --- Métodos de Controle da Janela Principal ---
    def minimize_window(self):
        try: self.root.iconify(); self.logger.info("Janela minimizada.")
        except Exception as e: self.logger.error(f"Erro minimizar: {e}")

    def close_window(self):
        """Fecha a aplicação de forma organizada."""
        if not self.running: return # Evita chamadas múltiplas
        self.logger.info("Iniciando processo de fechamento...")
        self.running = False # Sinaliza para parar loops

        # Cancela a próxima chamada de update_frames
        if hasattr(self, '_after_id_update') and self._after_id_update:
             try: self.root.after_cancel(self._after_id_update)
             except Exception: pass # Ignora se já cancelado ou root destruído
             self._after_id_update = None

        self.logger.info("Desconectando câmeras...")
        threads_to_join = []
        # Cria cópia da lista para iterar, caso disconnect modifique a original
        cameras_to_disconnect = list(self.cameras)
        for i, cam in enumerate(cameras_to_disconnect):
            if isinstance(cam, Camera):
                self.logger.debug(f"Chamando disconnect para câmera {i} (IP: {getattr(cam,'ip','N/A')})...")
                try:
                     cam.disconnect() # Chama o disconnect da câmera (que sinaliza a thread)
                     if cam.thread and cam.thread.is_alive():
                          threads_to_join.append(cam.thread) # Guarda thread para join
                except Exception as e: self.logger.error(f"Erro ao chamar disconnect para cam {i}: {e}")
            else: self.logger.warning(f"Ignorando item inválido {i} ao desconectar: {type(cam)}")

        # Espera as threads de leitura terminarem (opcional, mas recomendado)
        self.logger.debug(f"Aguardando {len(threads_to_join)} threads de câmera terminarem...")
        start_join = time.time()
        for t in threads_to_join:
            if t.is_alive():
                 t.join(timeout=1.0) # Espera curta por cada thread
        join_duration = time.time() - start_join
        self.logger.debug(f"Threads finalizadas ou timeout após {join_duration:.2f}s.")

        # Fecha janela da lista se aberta
        if self.camera_list_window and self.camera_list_window.winfo_exists():
             try: self.camera_list_window.destroy()
             except Exception: pass

        # Destroi a janela principal (com segurança)
        if self.root and self.root.winfo_exists():
            self.logger.info("Destruindo janela principal.")
            try: self.root.destroy()
            except tk.TclError: self.logger.warning("Erro Tcl ao destruir janela principal (provavelmente já fechada).")
            except Exception as e: self.logger.error(f"Erro ao destruir janela principal: {e}")
        self.logger.info("Aplicativo fechado.")

    # --- Funções Auxiliares ---
    def get_treeview_from_toplevel(self, toplevel: tk.Toplevel) -> ttk.Treeview | None:
        """Encontra o widget Treeview dentro de uma janela Toplevel ou Frame."""
        if not (toplevel and toplevel.winfo_exists()): return None
        try:
            # Procura diretamente nos filhos
            for widget in toplevel.winfo_children():
                if isinstance(widget, ttk.Treeview): return widget
            # Procura recursivamente dentro de frames filhos
            for widget in toplevel.winfo_children():
                if isinstance(widget, (tk.Frame, ttk.Frame)):
                    treeview = self.get_treeview_from_toplevel(widget)
                    if treeview: return treeview
            # self.logger.debug(f"Nenhuma Treeview encontrada na sub-árvore de: {toplevel}")
            return None
        except Exception as e:
            self.logger.error(f"Erro ao buscar Treeview em {toplevel}: {e}")
            return None

    # (FIM DA CLASSE CameraApp)