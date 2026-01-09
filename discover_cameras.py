#!/usr/bin/env python3
"""
Script para descobrir câmeras ONVIF na rede.
Uso: python3 discover_cameras.py
"""

import re
import sys


def discover_onvif_cameras(timeout: int = 10) -> list[dict]:
    """Descobre câmeras ONVIF na rede usando WS-Discovery."""

    try:
        from wsdiscovery import WSDiscovery
    except ImportError:
        print("ERRO: WSDiscovery não instalado.")
        print("Instale com: pip install WSDiscovery")
        return []

    print(f"Buscando câmeras ONVIF na rede (timeout: {timeout}s)...")
    print("-" * 50)

    cameras = []
    wsd = None

    try:
        wsd = WSDiscovery()
        wsd.start()

        # Criar tipo ONVIF para filtro
        class ONVIFType:
            def __init__(self):
                self.namespace = "http://www.onvif.org/ver10/network/wsdl"
                self.local_part = "NetworkVideoTransmitter"

            def getNamespace(self):
                return self.namespace

            def getLocalname(self):
                return self.local_part

            def getNamespacePrefix(self):
                return None

            def getFullname(self):
                return f"{{{self.namespace}}}{self.local_part}"

        # Buscar serviços
        services = wsd.searchServices(types=[ONVIFType()], timeout=timeout)

        existing_ips = set()

        for service in services:
            ip = None
            xaddrs = service.getXAddrs()

            # Extrair IP dos endereços
            if xaddrs:
                for xaddr in xaddrs:
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', xaddr)
                    if match:
                        potential_ip = match.group(1)
                        if potential_ip != "127.0.0.1":
                            ip = potential_ip
                            break

            # Tentar EPR se não encontrou IP
            if not ip:
                try:
                    epr = service.getEPR()
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', epr)
                    if match:
                        ip = match.group(1)
                except Exception:
                    pass

            if ip and ip not in existing_ips:
                existing_ips.add(ip)
                cameras.append({
                    "ip": ip,
                    "xaddrs": xaddrs,
                    "scopes": service.getScopes() if hasattr(service, 'getScopes') else [],
                })

        wsd.stop()

    except Exception as e:
        print(f"ERRO durante descoberta: {e}")
        if wsd:
            try:
                wsd.stop()
            except Exception:
                pass

    return cameras


def main():
    print("=" * 50)
    print("    DESCOBERTA DE CÂMERAS ONVIF")
    print("=" * 50)
    print()

    cameras = discover_onvif_cameras(timeout=10)

    if not cameras:
        print("\nNenhuma câmera ONVIF encontrada na rede.")
        print("\nPossíveis causas:")
        print("  - Não há câmeras ONVIF na rede")
        print("  - Firewall bloqueando porta UDP 3702")
        print("  - Câmeras em outra sub-rede")
        print("  - Multicast desabilitado no roteador")
        return 1

    print(f"\n{len(cameras)} câmera(s) encontrada(s):\n")
    print("-" * 50)

    for i, cam in enumerate(cameras, 1):
        print(f"\nCâmera {i}:")
        print(f"  IP: {cam['ip']}")
        if cam['xaddrs']:
            print(f"  Endereços: {', '.join(cam['xaddrs'][:2])}")

        # Tentar extrair informações dos scopes
        scopes = cam.get('scopes', [])
        for scope in scopes:
            scope_str = str(scope)
            if 'name' in scope_str.lower():
                print(f"  Scope: {scope_str}")

    print("\n" + "-" * 50)
    print("\nPara conectar, use:")
    print("  - ONVIF: IP + porta 80 + usuário/senha da câmera")
    print("  - RTSP: rtsp://usuario:senha@IP:554/stream")

    return 0


if __name__ == "__main__":
    sys.exit(main())
