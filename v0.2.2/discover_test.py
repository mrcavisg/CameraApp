# discover_test.py
from wsdiscovery import WSDiscovery
import logging
import sys
import time

# Logging básico para este teste
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger('discover_test')

logger.info("Iniciando WSDiscovery...")
wsd = None # Inicializa para o finally
try:
    wsd = WSDiscovery()
    wsd.start()
    logger.info("Buscando serviços por 10 segundos (sem filtro de tipo)...")

    # Tenta buscar TUDO que responde a WS-Discovery na rede
    services = wsd.searchServices(timeout=10)

    logger.info(f"Busca finalizada. Encontrados {len(services)} serviço(s).")
    print("-" * 30) # Separador

    if services:
        logger.info("--- Serviços Descobertos ---")
        for i, service in enumerate(services):
            print(f"\nServiço {i+1}:") # Usando print para garantir visibilidade
            try:
                # Tenta imprimir informações básicas de cada serviço
                types_str = [f"{{{t.getNamespace()}}}{t.getLocalname()}" for t in service.getTypes()]
                scopes_str = [str(s) for s in service.getScopes()] # Converte escopos para string
                xaddrs_str = service.getXAddrs()

                print(f"  Tipos (Types): {types_str}")
                print(f"  Escopos (Scopes): {scopes_str}")
                print(f"  Endereços (XAddrs): {xaddrs_str}")
                # Outras infos úteis se disponíveis
                if hasattr(service, 'getEPR'): print(f"  EPR: {service.getEPR()}")
                if hasattr(service, 'getMessageID'): print(f"  MessageID: {service.getMessageID()}")
                if hasattr(service, 'getInstanceId'): print(f"  InstanceId: {service.getInstanceId()}")

            except Exception as e:
                print(f"  Erro ao processar detalhes do serviço: {e}")
                # Tenta imprimir representação crua em caso de erro
                try: print(f"  Representação Crua: {service!r}")
                except: pass
        print("-" * 30)
    else:
        logger.warning("Nenhum dispositivo respondeu à busca WS-Discovery.")

except Exception as e:
    logger.critical(f"Erro durante a descoberta: {e}", exc_info=True)
finally:
    if wsd is not None:
         logger.info("Parando WSDiscovery...")
         try:
             # Verifica se stop existe e é chamável
             if hasattr(wsd, 'stop') and callable(wsd.stop):
                  wsd.stop()
                  logger.info("WSDiscovery parado.")
             else:
                  logger.warning("Objeto WSD não possui método stop() chamável.")
             # Pequena pausa para garantir que as threads fechem (opcional)
             time.sleep(0.5)
         except Exception as stop_e:
             logger.error(f"Erro ao parar WSDiscovery: {stop_e}")