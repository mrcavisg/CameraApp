# wsdl_utils.py
import os
import logging

def get_onvif_wsdl_files(wsdl_dir):
    """
    Verifica se o diretório WSDL existe e está pronto para uso.
    Não faz download, assume que os arquivos já estão disponíveis via onvif-zeep.
    
    Args:
        wsdl_dir (str): Diretório onde os arquivos WSDL devem estar.
    """
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(wsdl_dir):
        os.makedirs(wsdl_dir, exist_ok=True)
        logger.info(f"Diretório WSDL criado: {wsdl_dir}")
    
    # Não baixamos mais os arquivos, confiamos que onvif-zeep gerencia isso
    logger.info(f"Assumindo que os arquivos WSDL estão disponíveis em {wsdl_dir} ou via onvif-zeep.")
    return True  # Sempre retorna True, pois confiamos na biblioteca

if __name__ == '__main__':
    wsdl_dir = "wsdl"
    os.makedirs(wsdl_dir, exist_ok=True)
    get_onvif_wsdl_files(wsdl_dir)