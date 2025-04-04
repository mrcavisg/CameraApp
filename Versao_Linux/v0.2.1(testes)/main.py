# main.py
# Versão 0.2.1
import tkinter as tk
import logging
import os
import sys
# Tenta importar CameraApp, trata erro se app.py tiver problema
try:
    from app import CameraApp
except ImportError as import_err:
     print(f"ERRO CRÍTICO: Falha ao importar CameraApp de app.py: {import_err}", file=sys.stderr)
     # Mostra um erro simples se Tkinter puder ser inicializado minimamente
     try:
         root_err = tk.Tk(); root_err.withdraw() # Esconde janela principal
         tk.messagebox.showerror("Erro de Importação", f"Não foi possível carregar 'app.py'.\nVerifique o console para detalhes do erro:\n{import_err}")
         root_err.destroy()
     except Exception: pass # Ignora erros ao tentar mostrar messagebox
     sys.exit(1) # Sai se não conseguir importar
except Exception as general_err:
     # Captura outros erros durante a importação (ex: SyntaxError)
     print(f"ERRO CRÍTICO: Erro inesperado durante importação de app.py: {general_err}", file=sys.stderr)
     # Tenta mostrar erro para o usuário
     try:
         root_err = tk.Tk(); root_err.withdraw()
         tk.messagebox.showerror("Erro Crítico", f"Erro ao carregar o código principal (app.py).\nVerifique o console.\nErro: {general_err}")
         root_err.destroy()
     except Exception: pass
     sys.exit(1)

from utils import setup_logging # Importa a função de utils

def main():
    # Configura o logging usando a função de utils.py
    # Ela deve usar LOG_DIR de config.py internamente
    logger = setup_logging()
    logger.info("="*20 + " Aplicativo Iniciado " + "="*20)

    try:
        root = tk.Tk()
        # Passa a instância do logger configurada para a classe da aplicação
        app = CameraApp(root, logger)
        root.mainloop()
    except Exception as e:
        # Loga qualquer erro fatal que ocorra durante a inicialização ou execução
        logger.critical(f"Erro CRÍTICO não tratado na aplicação principal: {e}", exc_info=True)
        # (Opcional) Mostrar um erro para o usuário final
        try: tk.messagebox.showerror("Erro Crítico", f"Erro fatal:\n{e}\n\nConsulte logs.")
        except Exception: pass # Ignora erro se Tkinter já morreu
    finally:
        logger.info("="*20 + " Aplicativo Finalizado " + "="*20)

if __name__ == "__main__":
    main()