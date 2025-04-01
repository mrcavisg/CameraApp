import tkinter as tk
from tkinter import ttk, messagebox
import re
import numpy as np
import cv2
from PIL import Image, ImageTk
from camera import Camera
from utils import save_cameras, load_cameras
from config import FRAME_UPDATE_INTERVAL
from wsdiscovery import WSDiscovery
from wsdiscovery.service import Service
from onvif import ONVIFCamera

# Adicionar log para verificar a origem da classe Camera
import camera
import logging
logger = logging.getLogger(__name__)
logger.info(f"Classe Camera importada de: {Camera.__module__}")
logger.info(f"Módulo camera importado de: {camera.__file__}")

# Classe para simular o comportamento do QName
class SimpleQName:
    def __init__(self, namespace, local_part):
        self.namespace = namespace
        self.local_part = local_part

    def getNamespace(self):
        return self.namespace

    def getLocalPart(self):
        return self.local_part

class CameraApp:
    def __init__(self, root, logger):
        self.logger = logger
        self.logger.info("Inicializando CameraApp...")
        self.root = root
        self.root.title("CFA TECH - Camera App by CFA TECH")
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
        self.create_widgets()
        self.root.update_idletasks()
        self.center_window(self.root)

    def center_window(self, window):
        try:
            window.update_idletasks()
            width = window.winfo_width()
            height = window.winfo_height()
            x = (window.winfo_screenwidth() // 2) - (width // 2)
            y = (window.winfo_screenheight() // 2) - (height // 2)
            window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception as e:
            self.logger.error(f"Erro ao centralizar janela: {e}")

    def create_menu(self):
        try:
            menubar = tk.Menu(self.root)
            self.root.config(menu=menubar)

            camera_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Opções", menu=camera_menu)
            camera_menu.add_command(label="Gerenciar Câmeras", command=self.open_camera_list_window)
            camera_menu.add_separator()
            camera_menu.add_command(label="Minimizar", command=self.minimize_window)
            camera_menu.add_command(label="Sair", command=self.close_window)
            self.logger.info("Menu criado.")
        except Exception as e:
            self.logger.error(f"Erro ao criar menu: {e}")

    def create_widgets(self):
        try:
            self.frame_container = tk.Frame(self.root)
            self.frame_container.pack(expand=True, fill=tk.BOTH)

            self.load_cameras()
            self.start_cameras()
            self.create_video_labels()
            self.update_frames()
            self.logger.info("Widgets criados.")
        except Exception as e:
            self.logger.error(f"Erro ao criar widgets: {e}")

    def create_video_labels(self):
        try:
            for label in self.labels:
                label.destroy()
            self.labels = []
            self.aspect_ratios = []
            num_cameras = max(len(self.cameras), 1)
            rows = (num_cameras + 1) // 2
            for i in range(num_cameras):
                label = tk.Label(self.frame_container, bg="black")
                label.grid(row=i // 2, column=i % 2, sticky="nsew", padx=2, pady=2)
                self.labels.append(label)
                self.aspect_ratios.append("fit")
                self.add_context_menu(label, i)
            for i in range(rows):
                self.frame_container.grid_rowconfigure(i, weight=1)
            for i in range(2):
                self.frame_container.grid_columnconfigure(i, weight=1)
            self.logger.info(f"Labels de vídeo criados para {num_cameras} câmeras.")
        except Exception as e:
            self.logger.error(f"Erro ao criar labels de vídeo: {e}")

    def add_context_menu(self, label, index):
        try:
            menu = tk.Menu(label, tearoff=0)
            menu.add_command(label="Proporção 4:3", command=lambda: self.set_aspect_ratio(index, "4:3"))
            menu.add_command(label="Proporção 16:9", command=lambda: self.set_aspect_ratio(index, "16:9"))
            menu.add_command(label="Ajustar à Janela", command=lambda: self.set_aspect_ratio(index, "fit"))
            label.bind("<Button-3>", lambda event: menu.post(event.x_root, event.y_root))
        except Exception as e:
            self.logger.error(f"Erro ao adicionar menu de contexto: {e}")

    def set_aspect_ratio(self, index, ratio):
        try:
            self.aspect_ratios[index] = ratio
            self.logger.info(f"Proporção da câmera {index} ajustada para {ratio}")
        except Exception as e:
            self.logger.error(f"Erro ao ajustar proporção: {e}")

    def resize_frame(self, frame, label, aspect_ratio):
        try:
            label_width = label.winfo_width()
            label_height = label.winfo_height()

            if label_width <= 1 or label_height <= 1:
                label_width = 640
                label_height = 480

            frame_height, frame_width = frame.shape[:2]
            frame_ratio = frame_width / frame_height

            if aspect_ratio == "4:3":
                target_ratio = 4 / 3
            elif aspect_ratio == "16:9":
                target_ratio = 16 / 9
            else:
                return cv2.resize(frame, (label_width, label_height))

            if frame_ratio > target_ratio:
                new_height = int(label_width / target_ratio)
                new_width = label_width
            else:
                new_width = int(label_height * target_ratio)
                new_height = label_height

            frame = cv2.resize(frame, (new_width, new_height))

            if new_width != label_width or new_height != label_height:
                top = (label_height - new_height) // 2
                left = (label_width - new_width) // 2
                new_frame = np.zeros((label_height, label_width, 3), dtype=np.uint8)
                new_frame[top:top + new_height, left:left + new_width] = frame
                frame = new_frame

            return frame
        except Exception as e:
            self.logger.error(f"Erro ao redimensionar frame: {e}")
            return None

    def open_camera_list_window(self):
        try:
            if self.camera_list_window is not None and self.camera_list_window.winfo_exists():
                self.camera_list_window.lift()
                return

            self.camera_list_window = tk.Toplevel(self.root)
            self.camera_list_window.title("Gerenciar Câmeras")
            self.camera_list_window.geometry("800x400")
            self.center_window(self.camera_list_window)

            button_frame = tk.Frame(self.camera_list_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Adicionar Câmera ONVIF", command=self.add_onvif_camera_dialog).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Adicionar Câmera RTSP", command=self.add_rtsp_camera_dialog).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Editar Câmera", command=self.edit_camera_dialog).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Remover Câmera", command=self.remove_camera).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Buscar Câmeras", command=self.discover_cameras).pack(side=tk.LEFT, padx=5)

            self.camera_list = ttk.Treeview(
                self.camera_list_window, columns=("type", "ip", "port", "username", "rtsp_url", "status"), show="headings"
            )
            self.camera_list.heading("type", text="Tipo")
            self.camera_list.heading("ip", text="IP")
            self.camera_list.heading("port", text="Porta")
            self.camera_list.heading("username", text="Usuário")
            self.camera_list.heading("rtsp_url", text="URL RTSP")
            self.camera_list.heading("status", text="Status")
            self.camera_list.column("type", width=80)
            self.camera_list.column("port", width=50)
            self.camera_list.column("status", width=80)
            self.camera_list.pack(pady=10, fill=tk.BOTH, expand=True)

            for i, cam in enumerate(self.cameras):
                camera_type = "RTSP" if cam.rtsp_url else "ONVIF"
                status = "Conectado" if cam.connected else "Desconectado"
                self.camera_list.insert("", "end", values=(camera_type, cam.ip, cam.port, cam.username, cam.rtsp_url, status))

            self.camera_list_window.protocol("WM_DELETE_WINDOW", self.on_camera_list_window_close)
            self.logger.info("Janela de gerenciamento de câmeras aberta.")
        except Exception as e:
            self.logger.error(f"Erro ao abrir janela de gerenciamento de câmeras: {e}")

    def discover_cameras(self):
        """
        Realiza a busca automática de câmeras ONVIF na rede local e exibe na lista.
        """
        try:
            self.logger.info("Iniciando busca automática de câmeras ONVIF...")
            # Limpar a lista atual para evitar duplicatas
            for item in self.camera_list.get_children():
                self.camera_list.delete(item)

            # Usar WSDiscovery para encontrar câmeras ONVIF
            wsd = WSDiscovery()
            wsd.start()

            # Definir o tipo de serviço que queremos descobrir (ONVIF)
            # Criar um objeto SimpleQName para simular o comportamento esperado
            type_ = SimpleQName("http://www.onvif.org/ver10/network/wsdl", "NetworkVideoTransmitter")
            services = wsd.searchServices(types=[type_], timeout=5)  # Busca por 5 segundos

            discovered_cameras = []
            for service in services:
                # Extrair informações do serviço
                xaddrs = service.getXAddrs()
                for xaddr in xaddrs:
                    if "onvif" in xaddr.lower():
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', xaddr)
                        if ip_match:
                            ip = ip_match.group(1)
                            # Tentar conectar para obter mais informações
                            try:
                                onvif_cam = ONVIFCamera(ip, 80, "admin", "", wsdl_dir=None, no_cache=True)
                                device_info = onvif_cam.devicemgmt.GetDeviceInformation()
                                username = "admin"  # Usuário padrão, pode ser ajustado
                                port = 80  # Porta padrão ONVIF
                                rtsp_url = ""
                                status = "Descoberto (não conectado)"
                                discovered_cameras.append({
                                    "type": "ONVIF",
                                    "ip": ip,
                                    "port": port,
                                    "username": username,
                                    "rtsp_url": rtsp_url,
                                    "status": status
                                })
                                self.logger.info(f"Câmera ONVIF descoberta: IP={ip}, Fabricante={device_info.Manufacturer}")
                            except Exception as e:
                                self.logger.warning(f"Falha ao obter informações da câmera {ip}: {e}")
                                continue

            wsd.stop()

            # Adicionar câmeras descobertas à lista
            for cam in discovered_cameras:
                self.camera_list.insert("", "end", values=(
                    cam["type"], cam["ip"], cam["port"], cam["username"], cam["rtsp_url"], cam["status"]
                ))

            # Re-adicionar câmeras já conectadas
            for cam in self.cameras:
                camera_type = "RTSP" if cam.rtsp_url else "ONVIF"
                status = "Conectado" if cam.connected else "Desconectado"
                self.camera_list.insert("", "end", values=(camera_type, cam.ip, cam.port, cam.username, cam.rtsp_url, status))

            self.logger.info(f"Busca automática concluída. {len(discovered_cameras)} câmeras descobertas.")
            messagebox.showinfo("Busca Concluída", f"{len(discovered_cameras)} câmeras ONVIF encontradas na rede.", parent=self.camera_list_window)
        except Exception as e:
            self.logger.error(f"Erro durante a busca automática de câmeras: {e}")
            messagebox.showerror("Erro", f"Erro durante a busca de câmeras: {e}", parent=self.camera_list_window)

    def on_camera_list_window_close(self):
        try:
            self.camera_list_window.destroy()
            self.camera_list_window = None
            self.logger.info("Janela de gerenciamento de câmeras fechada.")
        except Exception as e:
            self.logger.error(f"Erro ao fechar janela de gerenciamento de câmeras: {e}")

    def add_onvif_camera_dialog(self):
        try:
            dialog = tk.Toplevel(self.camera_list_window if self.camera_list_window else self.root)
            dialog.title("Adicionar Câmera ONVIF")
            dialog.geometry("300x200")
            dialog.transient(self.camera_list_window if self.camera_list_window else self.root)
            dialog.grab_set()
            self.center_window(dialog)

            tk.Label(dialog, text="IP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            ip_entry = ttk.Entry(dialog)
            ip_entry.grid(row=0, column=1, padx=5, pady=5)

            tk.Label(dialog, text="Porta:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            port_entry = ttk.Entry(dialog)
            port_entry.grid(row=1, column=1, padx=5, pady=5)
            port_entry.insert(0, "80")

            tk.Label(dialog, text="Usuário:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
            user_entry = ttk.Entry(dialog)
            user_entry.grid(row=2, column=1, padx=5, pady=5)

            tk.Label(dialog, text="Senha:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
            password_entry = ttk.Entry(dialog, show="*")
            password_entry.grid(row=3, column=1, padx=5, pady=5)

            def save_camera():
                try:
                    ip = ip_entry.get()
                    try:
                        port = int(port_entry.get())
                    except ValueError:
                        messagebox.showerror("Erro", "Porta deve ser um número.", parent=dialog)
                        self.logger.error("Erro ao adicionar câmera ONVIF: Porta inválida.")
                        return
                    username = user_entry.get()
                    password = password_entry.get()

                    camera = Camera(ip, port, username, password, logger=self.logger)
                    self.logger.info(f"Tipo do objeto Camera criado: {type(camera)}")
                    if camera.connect(timeout=10):
                        self.cameras.append(camera)
                        self.camera_list.insert("", "end", values=("ONVIF", ip, port, username, camera.rtsp_url, "Conectado"))
                        save_cameras(self.cameras)
                        self.create_video_labels()
                        dialog.destroy()
                        self.logger.info(f"Câmera ONVIF adicionada: IP={ip}, Porta={port}, Usuário={username}, tipo: {type(camera)}")
                    else:
                        self.logger.error(f"Falha ao adicionar câmera ONVIF: IP={ip}")
                        messagebox.showerror("Erro", f"Falha ao conectar à câmera {ip}. Verifique os logs para mais detalhes.", parent=dialog)
                except Exception as e:
                    self.logger.error(f"Erro ao salvar câmera ONVIF: {e}")
                    messagebox.showerror("Erro", f"Erro ao salvar câmera: {e}", parent=dialog)

            save_button = ttk.Button(dialog, text="Salvar", command=save_camera)
            save_button.grid(row=4, column=0, columnspan=2, pady=10)

            dialog.bind("<Return>", lambda e: save_camera())
            dialog.bind("<Escape>", lambda e: dialog.destroy())
            self.logger.info("Diálogo de adicionar câmera ONVIF aberto.")
        except Exception as e:
            self.logger.error(f"Erro ao abrir diálogo de adicionar câmera ONVIF: {e}")

    def add_rtsp_camera_dialog(self):
        try:
            dialog = tk.Toplevel(self.camera_list_window if self.camera_list_window else self.root)
            dialog.title("Adicionar Câmera RTSP")
            dialog.geometry("400x150")
            dialog.transient(self.camera_list_window if self.camera_list_window else self.root)
            dialog.grab_set()
            self.center_window(dialog)

            tk.Label(dialog, text="URL RTSP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            rtsp_entry = ttk.Entry(dialog)
            rtsp_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
            dialog.grid_columnconfigure(1, weight=1)

            def save_camera():
                try:
                    rtsp_url = rtsp_entry.get()
                    if not re.match(r"^rtsp://[^\s]+$", rtsp_url):
                        messagebox.showerror("Erro", "URL RTSP inválida. Deve começar com rtsp://", parent=dialog)
                        self.logger.error(f"Erro ao adicionar câmera RTSP: URL inválida ({rtsp_url})")
                        return

                    try:
                        parts = rtsp_url.split("@")
                        user_pass = parts[0].replace("rtsp://", "") if len(parts) == 2 else ""
                        ip_port_path = parts[1] if len(parts) == 2 else parts[0].replace("rtsp://", "")
                        user, password = user_pass.split(":") if user_pass else ("", "")
                        ip_port = ip_port_path.split("/")[0]
                        ip = ip_port
                        port = 554
                        if ":" in ip_port:
                            ip, port_str = ip_port.split(":")
                            port = int(port_str)
                    except Exception as e:
                        messagebox.showerror("Erro", f"Erro ao analisar URL RTSP: {e}", parent=dialog)
                        self.logger.error(f"Erro ao analisar URL RTSP: {e}")
                        return

                    camera = Camera(ip, port, user, password, rtsp_url, logger=self.logger)
                    self.logger.info(f"Tipo do objeto Camera criado: {type(camera)}")
                    if camera.connect():
                        self.cameras.append(camera)
                        self.camera_list.insert("", "end", values=("RTSP", ip, port, user, rtsp_url, "Conectado"))
                        save_cameras(self.cameras)
                        self.create_video_labels()
                        dialog.destroy()
                        self.logger.info(f"Câmera RTSP adicionada: IP={ip}, Porta={port}, Usuário={user}, URL={rtsp_url}, tipo: {type(camera)}")
                    else:
                        self.logger.error(f"Falha ao adicionar câmera RTSP: URL={rtsp_url}")
                        messagebox.showerror("Erro", f"Falha ao conectar à câmera {rtsp_url}. Verifique os logs para mais detalhes.", parent=dialog)
                except Exception as e:
                    self.logger.error(f"Erro ao salvar câmera RTSP: {e}")
                    messagebox.showerror("Erro", f"Erro ao salvar câmera: {e}", parent=dialog)

            save_button = ttk.Button(dialog, text="Salvar", command=save_camera)
            save_button.grid(row=1, column=0, columnspan=2, pady=10)

            dialog.bind("<Return>", lambda e: save_camera())
            dialog.bind("<Escape>", lambda e: dialog.destroy())
            self.logger.info("Diálogo de adicionar câmera RTSP aberto.")
        except Exception as e:
            self.logger.error(f"Erro ao abrir diálogo de adicionar câmera RTSP: {e}")

    def edit_camera_dialog(self):
        try:
            selected_item = self.camera_list.selection()
            if not selected_item:
                messagebox.showwarning("Aviso", "Selecione uma câmera para editar.", parent=self.camera_list_window)
                self.logger.warning("Tentativa de editar câmera sem seleção.")
                return

            index = self.camera_list.index(selected_item[0])
            if index >= len(self.cameras):
                messagebox.showerror("Erro", "Índice de câmera inválido.", parent=self.camera_list_window)
                self.logger.error("Índice de câmera inválido ao tentar editar.")
                return

            camera = self.cameras[index]
            camera_type = "RTSP" if camera.rtsp_url else "ONVIF"

            dialog = tk.Toplevel(self.camera_list_window)
            dialog.title(f"Editar Câmera ({camera_type})")
            dialog.transient(self.camera_list_window)
            dialog.grab_set()
            if camera_type == "RTSP":
                dialog.geometry("400x150")
            else:
                dialog.geometry("300x200")
            self.center_window(dialog)

            if camera_type == "ONVIF":
                tk.Label(dialog, text="IP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
                ip_entry = ttk.Entry(dialog)
                ip_entry.grid(row=0, column=1, padx=5, pady=5)
                ip_entry.insert(0, camera.ip)

                tk.Label(dialog, text="Porta:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
                port_entry = ttk.Entry(dialog)
                port_entry.grid(row=1, column=1, padx=5, pady=5)
                port_entry.insert(0, str(camera.port))

                tk.Label(dialog, text="Usuário:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
                user_entry = ttk.Entry(dialog)
                user_entry.grid(row=2, column=1, padx=5, pady=5)
                user_entry.insert(0, camera.username)

                tk.Label(dialog, text="Senha:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
                password_entry = ttk.Entry(dialog, show="*")
                password_entry.grid(row=3, column=1, padx=5, pady=5)
                password_entry.insert(0, camera.password)

                def save_edited_camera():
                    try:
                        ip = ip_entry.get()
                        try:
                            port = int(port_entry.get())
                        except ValueError:
                            messagebox.showerror("Erro", "Porta deve ser um número.", parent=dialog)
                            self.logger.error("Erro ao editar câmera ONVIF: Porta inválida.")
                            return
                        username = user_entry.get()
                        password = password_entry.get()

                        # Desconectar a câmera antiga
                        camera.disconnect()
                        # Criar uma nova câmera com os dados atualizados
                        new_camera = Camera(ip, port, username, password, logger=self.logger)
                        self.logger.info(f"Tipo do objeto Camera criado (editado): {type(new_camera)}")
                        if new_camera.connect():
                            self.cameras[index] = new_camera
                            self.camera_list.item(selected_item[0], values=("ONVIF", ip, port, username, new_camera.rtsp_url, "Conectado"))
                            save_cameras(self.cameras)
                            self.create_video_labels()
                            dialog.destroy()
                            self.logger.info(f"Câmera ONVIF editada: IP={ip}, Porta={port}, Usuário={username}, tipo: {type(new_camera)}")
                        else:
                            self.logger.error(f"Falha ao reconectar câmera ONVIF após edição: IP={ip}")
                            messagebox.showerror("Erro", f"Falha ao reconectar à câmera {ip}. Verifique os logs para mais detalhes.", parent=dialog)
                    except Exception as e:
                        self.logger.error(f"Erro ao salvar câmera ONVIF editada: {e}")
                        messagebox.showerror("Erro", f"Erro ao salvar câmera: {e}", parent=dialog)

                save_button = ttk.Button(dialog, text="Salvar", command=save_edited_camera)
                save_button.grid(row=4, column=0, columnspan=2, pady=10)

            else:  # RTSP
                tk.Label(dialog, text="URL RTSP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
                rtsp_entry = ttk.Entry(dialog)
                rtsp_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
                rtsp_entry.insert(0, camera.rtsp_url)
                dialog.grid_columnconfigure(1, weight=1)

                def save_edited_camera():
                    try:
                        rtsp_url = rtsp_entry.get()
                        if not re.match(r"^rtsp://[^\s]+$", rtsp_url):
                            messagebox.showerror("Erro", "URL RTSP inválida. Deve começar com rtsp://", parent=dialog)
                            self.logger.error(f"Erro ao editar câmera RTSP: URL inválida ({rtsp_url})")
                            return

                        try:
                            parts = rtsp_url.split("@")
                            user_pass = parts[0].replace("rtsp://", "") if len(parts) == 2 else ""
                            ip_port_path = parts[1] if len(parts) == 2 else parts[0].replace("rtsp://", "")
                            user, password = user_pass.split(":") if user_pass else ("", "")
                            ip_port = ip_port_path.split("/")[0]
                            ip = ip_port
                            port = 554
                            if ":" in ip_port:
                                ip, port_str = ip_port.split(":")
                                port = int(port_str)
                        except Exception as e:
                            messagebox.showerror("Erro", f"Erro ao analisar URL RTSP: {e}", parent=dialog)
                            self.logger.error(f"Erro ao analisar URL RTSP: {e}")
                            return

                        # Desconectar a câmera antiga
                        camera.disconnect()
                        # Criar uma nova câmera com os dados atualizados
                        new_camera = Camera(ip, port, user, password, rtsp_url, logger=self.logger)
                        self.logger.info(f"Tipo do objeto Camera criado (editado): {type(new_camera)}")
                        if new_camera.connect():
                            self.cameras[index] = new_camera
                            self.camera_list.item(selected_item[0], values=("RTSP", ip, port, user, rtsp_url, "Conectado"))
                            save_cameras(self.cameras)
                            self.create_video_labels()
                            dialog.destroy()
                            self.logger.info(f"Câmera RTSP editada: IP={ip}, Porta={port}, Usuário={user}, URL={rtsp_url}, tipo: {type(new_camera)}")
                        else:
                            self.logger.error(f"Falha ao reconectar câmera RTSP após edição: URL={rtsp_url}")
                            messagebox.showerror("Erro", f"Falha ao reconectar à câmera {rtsp_url}. Verifique os logs para mais detalhes.", parent=dialog)
                    except Exception as e:
                        self.logger.error(f"Erro ao salvar câmera RTSP editada: {e}")
                        messagebox.showerror("Erro", f"Erro ao salvar câmera: {e}", parent=dialog)

                save_button = ttk.Button(dialog, text="Salvar", command=save_edited_camera)
                save_button.grid(row=1, column=0, columnspan=2, pady=10)

            dialog.bind("<Return>", lambda e: save_edited_camera())
            dialog.bind("<Escape>", lambda e: dialog.destroy())
            self.logger.info("Diálogo de edição de câmera aberto.")
        except Exception as e:
            self.logger.error(f"Erro ao abrir diálogo de edição de câmera: {e}")
            messagebox.showerror("Erro", f"Erro ao abrir diálogo de edição: {e}", parent=self.camera_list_window)

    def remove_camera(self):
        try:
            selected_item = self.camera_list.selection()
            if not selected_item:
                messagebox.showwarning("Aviso", "Selecione uma câmera para remover.", parent=self.camera_list_window)
                self.logger.warning("Tentativa de remover câmera sem seleção.")
                return

            index = self.camera_list.index(selected_item[0])
            if index < len(self.cameras):
                camera = self.cameras[index]
                if not isinstance(camera, Camera):
                    self.logger.error(f"Objeto na lista de câmeras (índice {index}) não é uma instância de Camera: {type(camera)}")
                else:
                    try:
                        camera.disconnect()
                    except AttributeError as e:
                        self.logger.error(f"Erro ao desconectar câmera (índice {index}): {e}, tipo do objeto: {type(camera)}")
                    self.logger.info(f"Câmera removida: IP={camera.ip}, RTSP_URL={camera.rtsp_url}")
                del self.cameras[index]
            self.camera_list.delete(selected_item[0])
            save_cameras(self.cameras)
            self.create_video_labels()
        except Exception as e:
            self.logger.error(f"Erro ao remover câmera: {e}")
            messagebox.showerror("Erro", f"Erro ao remover câmera: {e}", parent=self.camera_list_window)

    def minimize_window(self):
        try:
            self.root.iconify()
            self.logger.info("Janela minimizada.")
        except Exception as e:
            self.logger.error(f"Erro ao minimizar janela: {e}")

    def close_window(self):
        try:
            self.logger.info("Fechando aplicativo...")
            self.running = False
            for i, cam in enumerate(self.cameras):
                if not isinstance(cam, Camera):
                    self.logger.error(f"Objeto na lista de câmeras (índice {i}) não é uma instância de Camera: {type(cam)}")
                    continue
                try:
                    cam.disconnect()
                except AttributeError as e:
                    self.logger.error(f"Erro ao desconectar câmera (índice {i}): {e}, tipo do objeto: {type(cam)}")
            self.root.destroy()
            self.logger.info("Aplicativo fechado.")
        except Exception as e:
            self.logger.error(f"Erro ao fechar aplicativo: {e}")

    def load_cameras(self):
        try:
            data = load_cameras()  # Carrega os dados do JSON (lista de dicionários)
            self.cameras = []  # Limpa a lista atual para evitar duplicatas
            for cam_data in data:
                # Cria uma nova instância de Camera com os dados do JSON
                camera = Camera(
                    ip=cam_data["ip"],
                    port=cam_data["port"],
                    username=cam_data["username"],
                    password=cam_data["password"],
                    rtsp_url=cam_data.get("rtsp_url", ""),  # Usa .get() para evitar KeyError
                    logger=self.logger
                )
                self.cameras.append(camera)
                self.logger.info(f"Câmera carregada do JSON: {camera.ip}, tipo: {type(camera)}")
            self.logger.info(f"{len(self.cameras)} câmeras carregadas.")
        except Exception as e:
            self.logger.error(f"Erro ao carregar câmeras: {e}")
            messagebox.showerror("Erro", f"Erro ao carregar câmeras: {e}", parent=self.root)

    def start_cameras(self):
        try:
            self.logger.info("Iniciando conexão com câmeras...")
            for camera in self.cameras:
                if not camera.connected:
                    camera.connect()
        except Exception as e:
            self.logger.error(f"Erro ao iniciar câmeras: {e}")

    def update_frames(self):
        try:
            if not self.running:
                self.logger.info("Loop de atualização de frames interrompido.")
                return

            for i, camera in enumerate(self.cameras):
                if i < len(self.labels):
                    # Verifica se camera é uma instância de Camera
                    if not isinstance(camera, Camera):
                        self.logger.error(f"Objeto na lista de câmeras (índice {i}) não é uma instância de Camera: {type(camera)}")
                        continue
                    frame = camera.get_frame()
                    if frame is not None:
                        resized_frame = self.resize_frame(frame, self.labels[i], self.aspect_ratios[i])
                        if resized_frame is not None:
                            img = Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB))
                            imgtk = ImageTk.PhotoImage(image=img)
                            self.labels[i].config(image=imgtk)
                            self.labels[i].image = imgtk
                    if not camera.connected and self.camera_list_window and self.camera_list_window.winfo_exists():
                        current_values = list(self.camera_list.item(self.camera_list.get_children()[i])["values"])
                        current_values[-1] = "Desconectado"
                        self.camera_list.item(self.camera_list.get_children()[i], values=current_values)
                        self.logger.warning(f"Câmera {camera.ip} desconectada.")
            self.root.after(FRAME_UPDATE_INTERVAL, self.update_frames)
        except Exception as e:
            self.logger.error(f"Erro no loop de atualização de frames: {e}")
            if self.running:
                self.root.after(FRAME_UPDATE_INTERVAL, self.update_frames)