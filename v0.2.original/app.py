# app.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import re
import numpy as np
import cv2
from PIL import Image, ImageTk
from camera import Camera
# Usar as funções de utils que usam config.py
from utils import save_cameras, load_cameras
# Usar as constantes de config.py
from config import FRAME_UPDATE_INTERVAL, APP_NAME
from wsdiscovery import WSDiscovery
from wsdiscovery.service import Service
# Removido: from onvif import ONVIFCamera (não usado diretamente aqui)
import logging
import os

# Classe corrigida para compatibilidade com wsdiscovery
class SimpleQName:
    def __init__(self, namespace, local_part):
        self.namespace = namespace
        self.local_part = local_part

    def getNamespace(self):
        return self.namespace

    def getLocalname(self): # Alterado de getLocalPart para getLocalname
        return self.local_part

class CameraApp:
    def __init__(self, root, logger):
        self.logger = logger
        self.logger.info("Inicializando CameraApp...")
        self.root = root
        # Usar APP_NAME do config para o título
        self.root.title(f"{APP_NAME} by CFA TECH")
        self.root.geometry("1280x720")
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)
        self.cameras = []
        self.labels = []
        self.camera_list_window = None
        self.aspect_ratios = []
        self.running = True
        self.streaming_active = True # Flag para controlar a transmissão

        # Placeholder image (inicializado como None)
        self.placeholder_image = None
        self.placeholder_imgtk = None

        style = ttk.Style()
        style.theme_use("clam") # Ou outro tema: "default", "alt", "vista", etc.

        self.create_menu()
        self.create_widgets()
        # Criar um placeholder inicial com tamanho padrão ou baseado na janela
        self.create_placeholder_image(320, 240) # Ajuste o tamanho se necessário
        self.root.update_idletasks() # Atualiza a interface para obter tamanhos
        self.center_window(self.root)

        # Carregar e conectar câmeras DEPOIS de criar widgets e placeholder
        self.load_and_connect_cameras()
        # Iniciar o loop de atualização DEPOIS de carregar as câmeras
        self.update_frames() # Inicia o loop de atualização


    def create_placeholder_image(self, width, height):
        # Cria uma imagem cinza simples como placeholder
        try:
            # Cria uma imagem cinza
            img_array = np.full((height, width, 3), 128, dtype=np.uint8)
            # Adiciona texto centralizado
            text = "Pausado / Desconectado"
            text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            text_x = (width - text_size[0]) // 2
            text_y = (height + text_size[1]) // 2
            cv2.putText(img_array, text, (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

            self.placeholder_image = Image.fromarray(img_array)
            self.placeholder_imgtk = ImageTk.PhotoImage(image=self.placeholder_image)
            self.logger.info("Imagem de placeholder criada.")
        except Exception as e:
            self.logger.error(f"Erro ao criar placeholder: {e}")
            # Tentar criar um placeholder de texto simples se a imagem falhar
            self.placeholder_imgtk = None # Garante que é None


    def center_window(self, win):
        # Centraliza uma janela (principal ou Toplevel)
        win.update_idletasks()
        width = win.winfo_width()
        height = win.winfo_height()
        x = (win.winfo_screenwidth() // 2) - (width // 2)
        y = (win.winfo_screenheight() // 2) - (height // 2)
        win.geometry(f'{width}x{height}+{x}+{y}')
        win.deiconify() # Garante que a janela seja exibida se estava minimizada


    def create_menu(self):
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # Menu Arquivo
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label="Sair", command=self.close_window)
        self.menu_bar.add_cascade(label="Arquivo", menu=file_menu)

        # Menu Câmeras
        self.camera_menu = tk.Menu(self.menu_bar, tearoff=0) # Salvar referência ao menu
        self.camera_menu.add_command(label="Adicionar Câmera", command=self.add_camera_dialog)
        self.camera_menu.add_command(label="Gerenciar Câmeras", command=self.manage_cameras)
        self.camera_menu.add_command(label="Descobrir Câmeras ONVIF", command=self.discover_cameras)
        self.camera_menu.add_separator()
        # --- NOVOS ITENS DE MENU ---
        # Usar add_command diretamente retorna None, precisamos usar index para configurar estado depois
        self.camera_menu.add_command(label="Pausar Transmissões", command=self.pause_all_streams)
        self.camera_menu.add_command(label="Retomar Transmissões", command=self.resume_all_streams, state=tk.DISABLED) # Começa desabilitado
        # --- FIM NOVOS ITENS ---
        self.menu_bar.add_cascade(label="Câmeras", menu=self.camera_menu)


    def create_widgets(self):
        # Cria o frame principal onde as câmeras serão exibidas
        self.main_frame = ttk.Frame(self.root, padding="5")
        self.main_frame.pack(expand=True, fill=tk.BOTH)
        # Adicionar um label inicial caso não haja câmeras
        self.no_cameras_label = ttk.Label(self.main_frame, text="Carregando câmeras...", anchor=tk.CENTER)
        # Não empacotar ainda, será gerenciado em load_and_connect/setup_grid


    def load_and_connect_cameras(self):
        self.logger.info("Carregando câmeras do arquivo...")
        # Passar o logger para load_cameras
        loaded_cameras = load_cameras(logger=self.logger)
        self.cameras = [] # Limpar lista atual
        self.labels = [] # Limpar labels
        self.aspect_ratios = [] # Limpar aspect ratios

        # Limpar widgets antigos do frame principal
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        if not loaded_cameras:
            self.logger.info("Nenhuma câmera salva encontrada.")
            self.no_cameras_label.config(text="Nenhuma câmera configurada.\nUse o menu 'Câmeras' para adicionar.")
            self.no_cameras_label.pack(expand=True) # Mostrar o label se não houver câmeras
            return

        self.logger.info(f"{len(loaded_cameras)} câmeras carregadas.")
        connected_count = 0
        for cam_obj in loaded_cameras: # load_cameras retorna objetos Camera
            if not isinstance(cam_obj, Camera):
                self.logger.warning(f"Item inválido na lista carregada, não é um objeto Camera: {type(cam_obj)}")
                continue

            self.logger.info(f"Tentando conectar à câmera: {cam_obj.ip}")
            if cam_obj.connect():
                self.cameras.append(cam_obj)
                # Criar label com placeholder
                label = ttk.Label(self.main_frame, image=self.placeholder_imgtk, text="Conectando...", compound=tk.CENTER, anchor=tk.CENTER)
                self.labels.append(label)

                # Tentar pegar a resolução real para aspect ratio
                frame = cam_obj.get_frame() # Tenta pegar um frame inicial
                if frame is not None:
                    h, w = frame.shape[:2]
                    self.aspect_ratios.append(w / h if h > 0 else 16/9)
                else:
                    self.aspect_ratios.append(16/9) # Default aspect ratio
                connected_count += 1
            else:
                self.logger.warning(f"Falha ao conectar à câmera: {cam_obj.ip}. Câmera não será exibida.")
                # Opcional: poderia adicionar a câmera à lista mesmo desconectada
                # e mostrar um status "Falha na conexão" no grid.

        if self.cameras: # Somente configura o grid se houver câmeras conectadas
            self.setup_grid()
        elif loaded_cameras: # Se carregou mas nenhuma conectou
             self.no_cameras_label.config(text="Nenhuma câmera pôde ser conectada.\nVerifique as configurações ou a rede.")
             self.no_cameras_label.pack(expand=True)
        else: # Se não carregou nenhuma (já tratado no início)
             pass

        self.logger.info(f"{connected_count} de {len(loaded_cameras)} câmeras conectadas com sucesso.")


# app.py

# ... (outros métodos da classe CameraApp) ...

    def setup_grid(self):
         # --- REMOVA A LIMPEZA DE WIDGETS DESTA FUNÇÃO ---
         # A limpeza agora é feita apenas em load_and_connect_cameras
         # ---

         num_labels = len(self.labels) # Usa o número de labels que já existem na lista

         # Verifica se há labels para exibir
         if num_labels == 0:
             self.logger.info("Nenhum label para configurar no grid (nenhuma câmera conectada ou carregada).")
             # Garante que a mensagem de 'sem câmeras' seja exibida
             if self.no_cameras_label.winfo_exists(): # Verifica se o label de aviso existe
                 self.no_cameras_label.config(text="Nenhuma câmera conectada ou configurada.")
                 self.no_cameras_label.pack(expand=True, anchor=tk.CENTER) # Exibe a mensagem
             # Remove configurações de grid anteriores se houver
             if self.main_frame.winfo_exists():
                 cols, rows = self.main_frame.grid_size()
                 for i in range(cols): self.main_frame.columnconfigure(i, weight=0)
                 for i in range(rows): self.main_frame.rowconfigure(i, weight=0)
             return
         else:
             # Se há labels, garante que a mensagem 'sem câmeras' não esteja visível
             if self.no_cameras_label.winfo_exists():
                 self.no_cameras_label.pack_forget() # Esconde a mensagem

         # --- O resto da função permanece como estava ---
         self.logger.info(f"Configurando grid para {num_labels} câmeras.")
         cols = int(np.ceil(np.sqrt(num_labels)))
         rows = int(np.ceil(num_labels / cols))

         # Configurar peso das colunas e linhas para expansão proporcional
         for i in range(cols):
             self.main_frame.columnconfigure(i, weight=1)
         for i in range(rows):
             self.main_frame.rowconfigure(i, weight=1)

         # Adiciona os labels (que já existem e NÃO foram destruídos aqui) ao grid
         for i, label in enumerate(self.labels):
             row = i // cols
             col = i % cols
             # Verifica se o widget ainda existe antes de chamar grid (segurança extra)
             if label.winfo_exists():
                  label.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
             else:
                  # Isso não deveria acontecer agora, mas é um log útil se ocorrer
                  self.logger.warning(f"Tentativa de colocar no grid um label (índice {i}) que não existe mais (widget destruído inesperadamente?).")

# ... (resto da classe CameraApp) ...


    def resize_frame(self, frame, label_widget, aspect_ratio):
        # Redimensiona o frame para caber no label mantendo a proporção
        label_widget.update_idletasks() # Garante que temos o tamanho mais recente
        label_width = label_widget.winfo_width()
        label_height = label_widget.winfo_height()

        # Se o label ainda não tem tamanho definido, não redimensiona
        if label_width <= 1 or label_height <= 1:
            return None # Não pode redimensionar para tamanho 0 ou 1

        # Calcula as dimensões alvo mantendo o aspect ratio
        # Prioriza preencher a largura
        target_width = label_width
        target_height = int(target_width / aspect_ratio)

        # Se a altura calculada for maior que a do label, recalcula baseado na altura
        if target_height > label_height:
            target_height = label_height
            target_width = int(target_height * aspect_ratio)

        # Garante que as dimensões são pelo menos 1x1
        target_width = max(1, target_width)
        target_height = max(1, target_height)

        try:
            # Usar INTER_AREA para reduzir é geralmente melhor, INTER_LINEAR para aumentar
            interpolation = cv2.INTER_AREA if target_width < frame.shape[1] else cv2.INTER_LINEAR
            resized = cv2.resize(frame, (target_width, target_height), interpolation=interpolation)
            return resized
        except Exception as e:
            # Log detalhado do erro de redimensionamento
            self.logger.error(f"Erro ao redimensionar frame de {frame.shape[1]}x{frame.shape[0]} para {target_width}x{target_height}. Aspect: {aspect_ratio}. Label: {label_width}x{label_height}. Erro: {e}", exc_info=True)
            return None # Retorna None se o redimensionamento falhar


    def update_frames(self):
        # Loop principal para atualizar os frames das câmeras na GUI
        if not self.running:
            return # Sai se a aplicação estiver fechando

        try:
            active_cameras_count = len(self.cameras)
            active_labels_count = len(self.labels)

            # Checagem de segurança: se listas dessincronizaram
            if active_cameras_count != active_labels_count:
                 self.logger.warning(f"Dessincronização detectada: {active_cameras_count} câmeras vs {active_labels_count} labels. Reconfigurando grid.")
                 # Tentar recarregar e reconectar pode ser mais seguro
                 self.load_and_connect_cameras()
                 # Agendar próxima atualização e sair desta execução
                 if self.running:
                      self.root.after(FRAME_UPDATE_INTERVAL, self.update_frames)
                 return

            # Iterar sobre as câmeras e labels ativos
            for i in range(active_cameras_count):
                camera = self.cameras[i]
                current_label = self.labels[i]

                frame_processed = False # Flag para indicar se um frame foi exibido

                # --- LÓGICA DE PAUSA / BUSCA DE FRAME ---
                if self.streaming_active:
                    if not isinstance(camera, Camera):
                        self.logger.error(f"Item {i} não é Câmera: {type(camera)}")
                        # Marcar label como erro?
                        current_label.config(image=self.placeholder_imgtk, text="Erro Objeto")
                        current_label.image = self.placeholder_imgtk
                        continue # Pula para próxima câmera

                    frame = None
                    if camera.connected: # Só tenta pegar frame se já conectada
                        frame = camera.get_frame()

                    if frame is not None:
                        # Frame recebido com sucesso
                        aspect = self.aspect_ratios[i] if i < len(self.aspect_ratios) else 16/9
                        resized_frame = self.resize_frame(frame, current_label, aspect)

                        if resized_frame is not None:
                            try:
                                img = Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB))
                                imgtk = ImageTk.PhotoImage(image=img)
                                current_label.config(image=imgtk, text="") # Mostra frame, limpa texto
                                current_label.image = imgtk # Mantem referencia
                                frame_processed = True
                            except Exception as e:
                                 self.logger.error(f"Erro ao converter/exibir frame para câmera {camera.ip}: {e}", exc_info=True)
                                 # Mostrar placeholder em caso de erro de conversão/exibição
                                 current_label.config(image=self.placeholder_imgtk, text="Erro Exibição")
                                 current_label.image = self.placeholder_imgtk
                        else:
                             # Falha no resize, mostrar placeholder
                             current_label.config(image=self.placeholder_imgtk, text="Erro Resize")
                             current_label.image = self.placeholder_imgtk
                    else:
                        # Frame é None (pode ter desconectado ou erro na leitura)
                        if camera.connected: # Se estava conectada e falhou AGORA
                            self.logger.warning(f"Falha ao obter frame da câmera {camera.ip}. Marcando como desconectada.")
                            camera.connected = False # Marca como desconectada no objeto Camera
                        # Mostrar placeholder indicando desconexão (somente se não foi erro de objeto)
                        if isinstance(camera, Camera):
                            current_label.config(image=self.placeholder_imgtk, text="Desconectado")
                            current_label.image = self.placeholder_imgtk

                # --- FIM LÓGICA DE BUSCA/EXIBIÇÃO ---

                # Se NÃO estiver ativo (pausado manualmente)
                elif not self.streaming_active:
                    # Garantir que o placeholder de 'Pausado' seja exibido se não estiver mostrando um frame
                    # (A função pause_all_streams já faz isso, mas é um reforço)
                    if not frame_processed and current_label.cget("text") != "Pausado":
                        current_label.config(image=self.placeholder_imgtk, text="Pausado")
                        current_label.image = self.placeholder_imgtk

                # Atualizar status na lista de gerenciamento (Treeview) se a câmera desconectou
                if isinstance(camera, Camera) and not camera.connected:
                     self._update_camera_list_status(i, "Desconectado")

            # Agendar a próxima chamada de update_frames
            if self.running:
                self.root.after(FRAME_UPDATE_INTERVAL, self.update_frames)

        except Exception as e:
            # Captura erros inesperados no loop principal
            self.logger.error(f"Erro GERAL não esperado no loop de atualização: {e}", exc_info=True)
            # Tenta reagendar mesmo após erro para não parar completamente
            if self.running:
                self.root.after(FRAME_UPDATE_INTERVAL * 5, self.update_frames) # Aumenta intervalo após erro


    def _update_camera_list_status(self, index, status_text):
        """Helper para atualizar o status na Treeview da janela de gerenciamento."""
        if self.camera_list_window and self.camera_list_window.winfo_exists():
            try:
                children = self.camera_list.get_children()
                if 0 <= index < len(children):
                    item_id = children[index]
                    # Assumindo que status é a última coluna (índice 4 se colunas são IP,Port,User,RTSP,Status)
                    column_index_status = 4 # Ajuste se suas colunas forem diferentes
                    current_values = list(self.camera_list.item(item_id)["values"])

                    # Garante que a lista de valores tenha o tamanho esperado
                    while len(current_values) <= column_index_status:
                         current_values.append("") # Adiciona colunas vazias se necessário

                    # Atualiza apenas se o status mudou
                    if current_values[column_index_status] != status_text:
                        current_values[column_index_status] = status_text
                        self.camera_list.item(item_id, values=tuple(current_values)) # Treeview usa tupla
            except tk.TclError as e:
                 # Erro comum se a janela/widget foi destruído entre a verificação e o uso
                 self.logger.warning(f"Erro Tcl ao atualizar status na lista (janela fechada?): {e}")
            except Exception as e:
                self.logger.error(f"Erro inesperado ao atualizar status na lista de câmeras: {e}", exc_info=True)


    # --- FUNÇÕES DE PAUSA/RETOMADA ---
    def pause_all_streams(self):
        """Pausa a busca e exibição de frames de todas as câmeras."""
        if not self.streaming_active:
            self.logger.info("Transmissões já estão pausadas.")
            return

        self.logger.info("Pausando todas as transmissões.")
        self.streaming_active = False

        # Atualiza os labels para mostrar o placeholder "Pausado"
        for label in self.labels:
            if label.winfo_exists(): # Verifica se o label ainda existe
                 label.config(image=self.placeholder_imgtk, text="Pausado")
                 label.image = self.placeholder_imgtk

        # Atualiza estado dos itens de menu
        try:
            # camera_menu foi salvo em self.camera_menu
            if self.camera_menu:
                 pause_index = self.camera_menu.index("Pausar Transmissões")
                 resume_index = self.camera_menu.index("Retomar Transmissões")
                 self.camera_menu.entryconfig(pause_index, state=tk.DISABLED)
                 self.camera_menu.entryconfig(resume_index, state=tk.NORMAL)
        except tk.TclError as e:
            self.logger.error(f"Erro Tcl ao atualizar estado do menu (menu destruído?): {e}")
        except Exception as e:
            self.logger.error(f"Erro inesperado ao atualizar estado do menu 'Pausar': {e}")


    def resume_all_streams(self):
        """Retoma a busca e exibição de frames de todas as câmeras."""
        if self.streaming_active:
            self.logger.info("Transmissões já estão ativas.")
            return

        self.logger.info("Retomando todas as transmissões.")
        self.streaming_active = True

        # Limpa os placeholders (o update_frames vai buscar frames novos)
        # Coloca "Conectando..." temporariamente
        for label in self.labels:
             if label.winfo_exists():
                 label.config(image=self.placeholder_imgtk, text="Conectando...")
                 label.image = self.placeholder_imgtk

        # Atualiza estado dos itens de menu
        try:
             if self.camera_menu:
                 pause_index = self.camera_menu.index("Pausar Transmissões")
                 resume_index = self.camera_menu.index("Retomar Transmissões")
                 self.camera_menu.entryconfig(pause_index, state=tk.NORMAL)
                 self.camera_menu.entryconfig(resume_index, state=tk.DISABLED)
        except tk.TclError as e:
            self.logger.error(f"Erro Tcl ao atualizar estado do menu (menu destruído?): {e}")
        except Exception as e:
            self.logger.error(f"Erro inesperado ao atualizar estado do menu 'Retomar': {e}")

        # Não precisa chamar update_frames explicitamente, o loop agendado continuará


    # --- FUNÇÕES DE GERENCIAMENTO DE CÂMERAS (Originais + Ajustes) ---

    def add_camera_dialog(self):
        """Abre a janela de diálogo para adicionar uma nova câmera."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Adicionar Nova Câmera")
        dialog.transient(self.root) # Mantém sobre a janela principal
        dialog.grab_set() # Bloqueia interação com a janela principal

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(frame, text="IP:").grid(row=0, column=0, sticky="w", pady=2)
        ip_entry = ttk.Entry(frame, width=40)
        ip_entry.grid(row=0, column=1, pady=2)

        ttk.Label(frame, text="Porta ONVIF (80):").grid(row=1, column=0, sticky="w", pady=2)
        port_entry = ttk.Entry(frame, width=10)
        port_entry.grid(row=1, column=1, sticky="w", pady=2)
        port_entry.insert(0, "80") # Default ONVIF port

        ttk.Label(frame, text="Usuário:").grid(row=2, column=0, sticky="w", pady=2)
        user_entry = ttk.Entry(frame, width=40)
        user_entry.grid(row=2, column=1, pady=2)

        ttk.Label(frame, text="Senha:").grid(row=3, column=0, sticky="w", pady=2)
        pass_entry = ttk.Entry(frame, width=40, show="*")
        pass_entry.grid(row=3, column=1, pady=2)

        ttk.Label(frame, text="URL RTSP (opcional):").grid(row=4, column=0, sticky="w", pady=2)
        rtsp_entry = ttk.Entry(frame, width=40)
        rtsp_entry.grid(row=4, column=1, pady=2)
        ttk.Label(frame, text="Se preenchido, ignora ONVIF").grid(row=5, column=1, sticky="w", pady=2, padx=5)


        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        add_button = ttk.Button(
            button_frame, text="Adicionar",
            command=lambda: self.add_camera(
                ip_entry.get(), port_entry.get(), user_entry.get(),
                pass_entry.get(), rtsp_entry.get(), dialog
            )
        )
        add_button.pack(side=tk.RIGHT, padx=5)

        cancel_button = ttk.Button(button_frame, text="Cancelar", command=dialog.destroy)
        cancel_button.pack(side=tk.RIGHT)

        dialog.update_idletasks()
        self.center_window(dialog)


    def add_camera(self, ip, port_str, username, password, rtsp_url, dialog):
        """Valida dados, cria, conecta e adiciona a câmera."""
        if not ip:
            messagebox.showerror("Erro", "O endereço IP é obrigatório.", parent=dialog)
            return
        if not rtsp_url: # Se não for RTSP direto, usuário/senha/porta são importantes
             if not username:
                  messagebox.showerror("Erro", "O nome de usuário é obrigatório para conexão ONVIF.", parent=dialog)
                  return
             if not port_str:
                  messagebox.showerror("Erro", "A porta ONVIF é obrigatória.", parent=dialog)
                  return
             try:
                  port = int(port_str)
             except ValueError:
                  messagebox.showerror("Erro", "A porta ONVIF deve ser um número.", parent=dialog)
                  return
        else:
             port = 80 # Porta default se for RTSP direto (não usada na conexão RTSP)

        self.logger.info(f"Tentando adicionar nova câmera: IP={ip}, Porta={port}, User={username}, RTSP={'Sim' if rtsp_url else 'Não'}")

        # Cria a instância da câmera (passando o logger)
        new_cam = Camera(ip, port, username, password, rtsp_url, self.logger)

        # Tenta conectar
        if new_cam.connect():
            self.cameras.append(new_cam)

            # Adiciona label e aspect ratio
            label = ttk.Label(self.main_frame, image=self.placeholder_imgtk, text="Conectando...", compound=tk.CENTER, anchor=tk.CENTER)
            self.labels.append(label)
            frame = new_cam.get_frame() # Pega frame para aspect ratio
            if frame is not None:
                 h, w = frame.shape[:2]
                 self.aspect_ratios.append(w / h if h > 0 else 16/9)
            else:
                 self.aspect_ratios.append(16/9) # Default

            self.logger.info(f"Câmera {ip} adicionada e conectada com sucesso.")
            # Salva a lista atualizada usando a função de utils
            save_cameras(self.cameras, self.logger)
            # Reconfigura o grid para incluir a nova câmera
            self.setup_grid()
            # Atualiza a lista no gerenciador, se estiver aberto
            self.populate_camera_list()
            dialog.destroy()

            # Se estava pausado, configura o label da nova câmera como 'Pausado'
            if not self.streaming_active:
                 if label.winfo_exists():
                      label.config(image=self.placeholder_imgtk, text="Pausado")
                      label.image = self.placeholder_imgtk
        else:
            messagebox.showerror("Erro", f"Não foi possível conectar à câmera {ip}.\nVerifique os dados e a rede.", parent=dialog)
            self.logger.error(f"Falha ao conectar à câmera recém-adicionada: {ip}")
            # Não fecha o diálogo para permitir correção


    def manage_cameras(self):
        """Abre a janela para gerenciar câmeras existentes."""
        if self.camera_list_window and self.camera_list_window.winfo_exists():
            self.camera_list_window.lift()
            return

        self.camera_list_window = tk.Toplevel(self.root)
        self.camera_list_window.title("Gerenciar Câmeras")
        self.camera_list_window.geometry("800x400")
        self.camera_list_window.transient(self.root)
        self.camera_list_window.protocol("WM_DELETE_WINDOW", self.on_camera_list_close)

        frame = ttk.Frame(self.camera_list_window, padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        cols = ("ip", "port", "user", "rtsp", "status")
        self.camera_list = ttk.Treeview(frame, columns=cols, show="headings")

        self.camera_list.heading("ip", text="IP")
        self.camera_list.heading("port", text="Porta")
        self.camera_list.heading("user", text="Usuário")
        self.camera_list.heading("rtsp", text="URL RTSP")
        self.camera_list.heading("status", text="Status")

        self.camera_list.column("ip", width=150)
        self.camera_list.column("port", width=60, anchor=tk.CENTER)
        self.camera_list.column("user", width=100)
        self.camera_list.column("rtsp", width=250)
        self.camera_list.column("status", width=100, anchor=tk.CENTER)

        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.camera_list.yview)
        self.camera_list.configure(yscroll=scrollbar.set)
        self.camera_list.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        button_frame = ttk.Frame(self.camera_list_window, padding="5")
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Editar", command=self.edit_camera_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remover", command=self.remove_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Fechar", command=self.on_camera_list_close).pack(side=tk.RIGHT, padx=5)

        self.populate_camera_list() # Preenche a lista
        self.center_window(self.camera_list_window)


    def populate_camera_list(self):
        """Preenche a Treeview na janela de gerenciamento."""
        if not (self.camera_list_window and self.camera_list_window.winfo_exists()):
            return # Sai se a janela não existe

        # Limpa a lista antiga
        for item in self.camera_list.get_children():
            self.camera_list.delete(item)

        # Adiciona câmeras da lista self.cameras
        for i, cam in enumerate(self.cameras):
            if isinstance(cam, Camera):
                 status = "Conectado" if cam.connected else "Desconectado"
                 # Adiciona uma tag para estilização futura, se desejado
                 tag = "connected" if cam.connected else "disconnected"
                 values = (
                     cam.ip,
                     str(cam.port), # Converte porta para string
                     cam.username,
                     cam.rtsp_url if cam.rtsp_url else "-", # Mostrar '-' se não houver URL RTSP direto
                     status
                 )
                 self.camera_list.insert("", tk.END, values=values, tags=(tag,))
            else:
                 self.logger.warning(f"Item inválido {i} na lista de câmeras ao popular Treeview.")

        # Configurar tags (opcional)
        self.camera_list.tag_configure("disconnected", foreground="red")
        self.camera_list.tag_configure("connected", foreground="green")


    def discover_cameras(self):
        """Usa WSDiscovery para encontrar câmeras ONVIF na rede."""
        self.logger.info("Iniciando descoberta de câmeras ONVIF...")
        try:
            wsd = WSDiscovery()
            wsd.start()
            # Procurar por dispositivos de rede ('NetworkVideoTransmitter')
            # A classe SimpleQName foi definida no início do arquivo
            qname = SimpleQName("http://www.onvif.org/ver10/network/wsdl", "NetworkVideoTransmitter")
            services = wsd.searchServices(types=[qname])
            wsd.stop()
        except Exception as e:
             self.logger.error(f"Erro durante a descoberta WS-Discovery: {e}", exc_info=True)
             messagebox.showerror("Erro de Descoberta", f"Falha ao executar a descoberta de rede.\nVerifique o firewall ou dependências.\nErro: {e}")
             return

        if not services:
            self.logger.info("Nenhuma câmera ONVIF encontrada na rede.")
            messagebox.showinfo("Descoberta ONVIF", "Nenhuma câmera ONVIF encontrada na rede local.")
            return

        self.logger.info(f"{len(services)} dispositivos ONVIF encontrados.")

        # Janela para exibir resultados da descoberta
        discover_window = tk.Toplevel(self.root)
        discover_window.title("Câmeras ONVIF Encontradas")
        discover_window.geometry("500x300")
        discover_window.transient(self.root)
        discover_window.grab_set()

        frame = ttk.Frame(discover_window, padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        listbox = tk.Listbox(frame, width=70, height=10)
        listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        discovered_cameras_info = [] # Lista para guardar (IP, Porta, XAddrs)
        for service in services:
            try:
                # O IP pode estar em xAddrs ou getHost() dependendo da implementação
                ip = service.getEPR() # Ou service.getHost() ? Testar qual funciona melhor
                # Tenta extrair IP de URLs complexas se necessário
                ip_match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", ip)
                if ip_match:
                     ip = ip_match.group(1)
                else:
                     # Tentar obter do getXAddrs se EPR não for IP direto
                     if service.getXAddrs():
                          addr_match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", service.getXAddrs()[0])
                          if addr_match:
                               ip = addr_match.group(1)
                          else:
                               ip = "IP Desconhecido" # Fallback
                     else:
                          ip = "IP Desconhecido"


                port = 80 # Porta padrão ONVIF, WSD geralmente não retorna a porta de serviço ONVIF exata
                xaddrs = service.getXAddrs() # Guardar os endereços para referência

                # Evitar duplicatas na exibição (baseado no IP)
                if ip != "IP Desconhecido" and ip not in [info[0] for info in discovered_cameras_info]:
                    display_text = f"IP: {ip} (Endereços: {xaddrs})"
                    listbox.insert(tk.END, display_text)
                    discovered_cameras_info.append((ip, port, xaddrs)) # Guardar info
            except Exception as e:
                self.logger.warning(f"Erro ao processar serviço descoberto: {e} - Serviço: {service}")


        button_frame = ttk.Frame(discover_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def on_add_selected():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                selected_info = discovered_cameras_info[index]
                self.add_discovered_camera(selected_info, discover_window)
            else:
                messagebox.showwarning("Aviso", "Selecione uma câmera da lista para adicionar.", parent=discover_window)

        ttk.Button(button_frame, text="Adicionar Selecionada", command=on_add_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Fechar", command=discover_window.destroy).pack(side=tk.RIGHT, padx=5)

        self.center_window(discover_window)


    def add_discovered_camera(self, camera_info, discover_window):
        """Pede credenciais e adiciona uma câmera descoberta."""
        ip, port, xaddrs = camera_info
        self.logger.info(f"Adicionando câmera descoberta: IP={ip}, Porta={port}")

        # Pedir usuário e senha
        user = simpledialog.askstring("Credenciais ONVIF", f"Usuário para a câmera {ip}:", parent=discover_window)
        if user is None: # Cancelado
            return
        password = simpledialog.askstring("Credenciais ONVIF", f"Senha para a câmera {ip}:", show='*', parent=discover_window)
        if password is None: # Cancelado
            return

        # Cria a instância da câmera (sem URL RTSP inicial, será descoberto)
        # Passa o logger
        new_cam = Camera(ip, port, user, password, "", self.logger)

        # Tenta conectar (isso deve buscar o RTSP via ONVIF)
        if new_cam.connect():
            self.cameras.append(new_cam)
            # Adiciona label e aspect ratio
            label = ttk.Label(self.main_frame, image=self.placeholder_imgtk, text="Conectando...", compound=tk.CENTER, anchor=tk.CENTER)
            self.labels.append(label)
            frame = new_cam.get_frame() # Pega frame inicial se possível
            if frame is not None:
                 h, w = frame.shape[:2]
                 self.aspect_ratios.append(w / h if h > 0 else 16/9)
            else:
                 self.aspect_ratios.append(16/9)

            self.logger.info(f"Câmera descoberta {ip} adicionada e conectada com sucesso.")
            # Salva a lista atualizada
            save_cameras(self.cameras, self.logger)
            # Reconfigura o grid
            self.setup_grid()
            # Atualiza a lista no gerenciador
            self.populate_camera_list()
            # Fechar janela de descoberta? Ou permitir adicionar mais?
            # discover_window.destroy() # Descomente para fechar após adicionar uma

            # Ajustar estado visual se pausado
            if not self.streaming_active:
                 if label.winfo_exists():
                      label.config(image=self.placeholder_imgtk, text="Pausado")
                      label.image = self.placeholder_imgtk
        else:
            messagebox.showerror("Erro", f"Não foi possível conectar à câmera ONVIF {ip} com as credenciais fornecidas.", parent=discover_window)
            self.logger.error(f"Falha ao conectar à câmera ONVIF descoberta: {ip}")


    def remove_camera(self):
        """Remove a câmera selecionada na janela de gerenciamento."""
        if not (self.camera_list_window and self.camera_list_window.winfo_exists()):
            messagebox.showerror("Erro", "A janela de gerenciamento não está aberta.")
            return

        selected_items = self.camera_list.selection()
        if not selected_items:
            messagebox.showwarning("Aviso", "Selecione uma câmera para remover.", parent=self.camera_list_window)
            return

        item_id = selected_items[0]
        # O índice na Treeview pode não corresponder diretamente ao índice na lista self.cameras
        # se a Treeview for reordenada. É melhor encontrar pelo IP.
        try:
            selected_values = self.camera_list.item(item_id)["values"]
            selected_ip = selected_values[0] # Assume que IP é a primeira coluna
        except IndexError:
             messagebox.showerror("Erro", "Não foi possível obter informações da câmera selecionada.", parent=self.camera_list_window)
             return


        # Encontrar o índice real na lista self.cameras
        index_to_remove = -1
        for i, cam in enumerate(self.cameras):
             if isinstance(cam, Camera) and cam.ip == selected_ip:
                  index_to_remove = i
                  break

        if index_to_remove != -1:
            if messagebox.askyesno("Confirmar Remoção", f"Tem certeza que deseja remover a câmera {selected_ip}?", parent=self.camera_list_window):
                cam_to_remove = self.cameras[index_to_remove]
                self.logger.info(f"Removendo câmera: {cam_to_remove.ip}")

                # Desconectar a câmera antes de remover
                cam_to_remove.disconnect()

                # Remover da lista de câmeras, labels e aspect ratios
                del self.cameras[index_to_remove]
                if index_to_remove < len(self.aspect_ratios): # Segurança
                     del self.aspect_ratios[index_to_remove]
                if index_to_remove < len(self.labels): # Segurança
                     label_to_remove = self.labels.pop(index_to_remove)
                     if label_to_remove.winfo_exists():
                          label_to_remove.destroy()

                # Salvar alterações
                save_cameras(self.cameras, self.logger)
                # Atualizar a Treeview
                self.populate_camera_list() # Repopula a lista (remove o item visualmente)
                # Reorganizar o grid principal
                self.setup_grid()
                self.logger.info(f"Câmera {cam_to_remove.ip} removida.")
        else:
            self.logger.error(f"Câmera com IP {selected_ip} selecionada na lista, mas não encontrada em self.cameras.")
            messagebox.showerror("Erro", f"Erro interno: Câmera {selected_ip} não encontrada para remoção.", parent=self.camera_list_window)


    def edit_camera_dialog(self):
        """Abre o diálogo para editar a câmera selecionada."""
        if not (self.camera_list_window and self.camera_list_window.winfo_exists()):
             messagebox.showerror("Erro", "A janela de gerenciamento não está aberta.")
             return

        selected_items = self.camera_list.selection()
        if not selected_items:
            messagebox.showwarning("Aviso", "Selecione uma câmera para editar.", parent=self.camera_list_window)
            return

        item_id = selected_items[0]
        try:
             selected_values = self.camera_list.item(item_id)["values"]
             selected_ip = selected_values[0]
        except IndexError:
             messagebox.showerror("Erro", "Não foi possível obter informações da câmera selecionada.", parent=self.camera_list_window)
             return

        # Encontrar o índice real na lista self.cameras
        original_index = -1
        for i, cam in enumerate(self.cameras):
             if isinstance(cam, Camera) and cam.ip == selected_ip:
                  original_index = i
                  break

        if original_index == -1:
             messagebox.showerror("Erro", f"Erro interno: Câmera {selected_ip} não encontrada para edição.", parent=self.camera_list_window)
             return

        original_cam = self.cameras[original_index]

        # Cria a janela de diálogo de edição
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Editar Câmera: {original_cam.ip}")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        # Campos preenchidos com dados atuais (IP não pode ser editado aqui, é o identificador)
        ttk.Label(frame, text="IP:").grid(row=0, column=0, sticky="w", pady=2)
        ip_label = ttk.Label(frame, text=original_cam.ip) # Mostra IP, mas não permite edição
        ip_label.grid(row=0, column=1, pady=2, sticky="w")

        ttk.Label(frame, text="Porta ONVIF:").grid(row=1, column=0, sticky="w", pady=2)
        port_entry = ttk.Entry(frame, width=10)
        port_entry.grid(row=1, column=1, sticky="w", pady=2)
        port_entry.insert(0, str(original_cam.port))

        ttk.Label(frame, text="Usuário:").grid(row=2, column=0, sticky="w", pady=2)
        user_entry = ttk.Entry(frame, width=40)
        user_entry.grid(row=2, column=1, pady=2)
        user_entry.insert(0, original_cam.username)

        ttk.Label(frame, text="Senha:").grid(row=3, column=0, sticky="w", pady=2)
        pass_entry = ttk.Entry(frame, width=40, show="*")
        pass_entry.grid(row=3, column=1, pady=2)
        pass_entry.insert(0, original_cam.password) # Preenche com senha atual

        ttk.Label(frame, text="URL RTSP (opcional):").grid(row=4, column=0, sticky="w", pady=2)
        rtsp_entry = ttk.Entry(frame, width=40)
        rtsp_entry.grid(row=4, column=1, pady=2)
        rtsp_entry.insert(0, original_cam.rtsp_url if original_cam.rtsp_url else "")
        ttk.Label(frame, text="Se preenchido, ignora ONVIF").grid(row=5, column=1, sticky="w", pady=2, padx=5)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        update_button = ttk.Button(
            button_frame, text="Atualizar",
            command=lambda: self.update_camera(
                original_index, # Passa o índice original
                original_cam.ip, # IP não muda
                port_entry.get(),
                user_entry.get(),
                pass_entry.get(),
                rtsp_entry.get(),
                dialog
            )
        )
        update_button.pack(side=tk.RIGHT, padx=5)

        cancel_button = ttk.Button(button_frame, text="Cancelar", command=dialog.destroy)
        cancel_button.pack(side=tk.RIGHT)

        self.center_window(dialog)


    def update_camera(self, index, ip, port_str, username, password, rtsp_url, dialog):
        """Atualiza os dados da câmera após edição."""
        # Validação similar ao add_camera
        if not rtsp_url: # Se não for RTSP direto, usuário/senha/porta são importantes
             if not username:
                  messagebox.showerror("Erro", "O nome de usuário é obrigatório para conexão ONVIF.", parent=dialog)
                  return
             if not port_str:
                  messagebox.showerror("Erro", "A porta ONVIF é obrigatória.", parent=dialog)
                  return
             try:
                  port = int(port_str)
             except ValueError:
                  messagebox.showerror("Erro", "A porta ONVIF deve ser um número.", parent=dialog)
                  return
        else:
             port = 80 # Porta default não usada

        if index < 0 or index >= len(self.cameras):
            messagebox.showerror("Erro", "Erro interno: Índice da câmera inválido.", parent=dialog)
            return

        cam_to_update = self.cameras[index]
        self.logger.info(f"Atualizando câmera: {ip}")

        # Desconectar a câmera antiga antes de atualizar e reconectar
        cam_to_update.disconnect()

        # Atualizar os dados no objeto Camera existente
        cam_to_update.port = port
        cam_to_update.username = username
        cam_to_update.password = password
        cam_to_update.rtsp_url = rtsp_url # Atualiza URL RTSP (se foi fornecida ou removida)

        # Tentar reconectar com os novos dados
        if cam_to_update.connect():
            self.logger.info(f"Câmera {ip} atualizada e reconectada com sucesso.")
            # Atualizar o aspect ratio se a conexão foi bem sucedida (pode ter mudado o stream)
            frame = cam_to_update.get_frame()
            if frame is not None:
                 h, w = frame.shape[:2]
                 self.aspect_ratios[index] = w / h if h > 0 else 16/9
            else:
                 self.aspect_ratios[index] = 16/9 # Mantém default se não conseguir frame

            save_cameras(self.cameras, self.logger) # Salva as alterações
            self.populate_camera_list() # Atualiza a Treeview
            dialog.destroy()

            # Configura o label para "Conectando..." ou "Pausado"
            label = self.labels[index]
            if label.winfo_exists():
                 if self.streaming_active:
                      label.config(image=self.placeholder_imgtk, text="Conectando...")
                 else:
                      label.config(image=self.placeholder_imgtk, text="Pausado")
                 label.image = self.placeholder_imgtk

        else:
            messagebox.showerror("Erro", f"Não foi possível reconectar à câmera {ip} com os novos dados.", parent=dialog)
            self.logger.error(f"Falha ao reconectar câmera {ip} após atualização.")
            # Não fecha o diálogo, permite tentar novamente
            # Reverter alterações no objeto? Ou manter e mostrar desconectado?
            # Por enquanto, mantém alterado e ficará desconectado.


    def on_camera_list_close(self):
        """Chamado ao fechar a janela de gerenciamento."""
        if self.camera_list_window:
            self.camera_list_window.destroy()
            self.camera_list_window = None # Importante resetar a variável


    def close_window(self):
        """Chamado ao fechar a janela principal da aplicação."""
        self.logger.info("Fechando a aplicação...")
        self.running = False # Sinaliza para parar o loop update_frames
        self.streaming_active = False # Garante que não tentará pegar frames ao fechar

        # Esperar um ciclo de eventos para permitir que o loop pare (opcional)
        # self.root.after(50, self._finish_closing)
        self._finish_closing() # Chamar diretamente


    def _finish_closing(self):
        """Finaliza o fechamento: desconecta câmeras e destrói a janela."""
        self.logger.info("Desconectando câmeras...")
        # Desconectar todas as câmeras
        for camera in self.cameras:
            try:
                 # Garantir que é um objeto Camera válido
                 if isinstance(camera, Camera):
                      camera.disconnect()
            except Exception as e:
                # Logar erro mas continuar desconectando as outras
                self.logger.error(f"Erro ao desconectar câmera {getattr(camera, 'ip', 'IP DESCONHECIDO')} ao fechar: {e}")

        # Fechar janela de gerenciamento se estiver aberta
        if self.camera_list_window and self.camera_list_window.winfo_exists():
            try:
                self.camera_list_window.destroy()
            except tk.TclError:
                pass # Ignora erro se já foi destruída

        # Fechar a janela principal
        try:
            self.root.destroy()
            self.logger.info("Janela principal destruída. Aplicação finalizada.")
        except tk.TclError:
             self.logger.warning("Janela principal Tkinter já havia sido destruída.")

# Fim da classe CameraApp