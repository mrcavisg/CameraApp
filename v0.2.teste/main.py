# main.py
import tkinter as tk
import logging
import os
import sys
from app import CameraApp
from utils import setup_logging # Importa a função corrigida de utils

# Não precisa importar LOG_DIR aqui se setup_logging usa config internamente
# from config import LOG_DIR

def main():
    # 1. Configura o logging chamando a função de utils.py
    #    setup_logging agora usa os paths de config.py internamente (ou fallbacks)
    logger = setup_logging()
    logger.info("="*20 + " Aplicativo Iniciado " + "="*20)

    try:
        root = tk.Tk()
        # 2. Passa a instância do logger configurada para a classe da aplicação
        app = CameraApp(root, logger)
        root.mainloop()
    except Exception as e:
        # Loga qualquer erro fatal que ocorra durante a inicialização ou execução
        # O erro AttributeError que vimos antes ocorreria aqui dentro ao chamar CameraApp
        logger.critical(f"Erro CRÍTICO não tratado na aplicação principal: {e}", exc_info=True)
        # (Opcional) Mostrar um erro para o usuário final
        # import tkinter.messagebox
        # tkinter.messagebox.showerror("Erro Crítico", f"O aplicativo encontrou um erro fatal e precisa ser fechado.\n\n{e}\n\nConsulte os logs para detalhes.")
    finally:
        logger.info("="*20 + " Aplicativo Finalizado " + "="*20)

if __name__ == "__main__":
    main()