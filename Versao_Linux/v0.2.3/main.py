# main.py
# Versão 0.2.3 criada em 15/08/2023
import tkinter as tk
import logging
import os
import sys
import threading # Importa threading

# Importa utils PRIMEIRO para configurar logging ANTES de importar app
try:
    # Assegura que config.py seja encontrado (adiciona diretório pai ao path se necessário)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path: sys.path.insert(0, current_dir)
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path: sys.path.insert(0, parent_dir)

    from utils import setup_logging
    from config import LOGGER_NAME # Importa para passar o nome correto
except ImportError as e:
     print(f"ERRO CRÍTICO: Falha ao importar utils.py ou config.py: {e}", file=sys.stderr)
     sys.exit(1)

# Configura o logger ANTES de importar app
logger = setup_logging() # Usa a função de utils

# Agora tenta importar CameraApp
try:
    from app import CameraApp
except ImportError as import_err:
     logger.critical(f"Falha ao importar CameraApp de app.py: {import_err}", exc_info=True)
     try: # Tenta mostrar erro gráfico como fallback
         root_err = tk.Tk(); root_err.withdraw()
         tk.messagebox.showerror("Erro de Importação", f"Não foi possível carregar 'app.py'.\nVerifique os logs.\nErro: {import_err}")
         root_err.destroy()
     except Exception: pass
     sys.exit(1)
except Exception as general_err:
     logger.critical(f"Erro inesperado durante importação de app.py: {general_err}", exc_info=True)
     try:
         root_err = tk.Tk(); root_err.withdraw()
         tk.messagebox.showerror("Erro Crítico", f"Erro ao carregar o código principal (app.py).\nVerifique os logs.\nErro: {general_err}")
         root_err.destroy()
     except Exception: pass
     sys.exit(1)


def main():
    logger.info("="*20 + " Aplicativo Iniciado " + "="*20)
    root = None # Inicializa root
    try:
        root = tk.Tk()
        # Passa a instância do logger configurada para CameraApp
        app = CameraApp(root, logger)
        root.mainloop()
    except Exception as e:
        logger.critical(f"Erro CRÍTICO não tratado na aplicação principal: {e}", exc_info=True)
        try:
            if root and root.winfo_exists():
                 tk.messagebox.showerror("Erro Crítico", f"Erro fatal:\n{e}\n\nConsulte logs.")
        except Exception: pass
    finally:
        logger.info("="*20 + " Aplicativo Finalizado " + "="*20)

if __name__ == "__main__":
    # Define o nome da thread principal
    threading.current_thread().name = "MainThread"
    main()