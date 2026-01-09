#!/usr/bin/env python3
"""
Scanner de câmeras IP em qualquer faixa de rede.
Procura por portas comuns de câmeras (RTSP, HTTP).

Uso: python3 scan_cameras.py 192.168.1.0/24
     python3 scan_cameras.py 10.0.0.1-10.0.0.254
"""

import argparse
import ipaddress
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# Portas comuns de câmeras IP
CAMERA_PORTS = {
    554: "RTSP",
    80: "HTTP",
    8080: "HTTP Alt",
    8000: "Hikvision",
    8899: "Intelbras",
    443: "HTTPS",
    37777: "Dahua",
    34567: "DVR Generic",
}


def check_port(ip: str, port: int, timeout: float = 1.0) -> Optional[tuple]:
    """Verifica se uma porta está aberta em um IP."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        if result == 0:
            return (ip, port, CAMERA_PORTS.get(port, "Unknown"))
        return None
    except Exception:
        return None


def parse_ip_range(ip_range: str) -> list[str]:
    """Parse uma faixa de IPs (CIDR ou range)."""
    ips = []

    try:
        # Tentar CIDR (ex: 192.168.1.0/24)
        network = ipaddress.ip_network(ip_range, strict=False)
        for ip in network.hosts():
            ips.append(str(ip))
    except ValueError:
        # Tentar range (ex: 192.168.1.1-192.168.1.254)
        if "-" in ip_range:
            parts = ip_range.split("-")
            if len(parts) == 2:
                start_ip = ipaddress.ip_address(parts[0].strip())

                # Se o segundo é só o último octeto
                end_part = parts[1].strip()
                if "." not in end_part:
                    base = ".".join(parts[0].split(".")[:-1])
                    end_ip = ipaddress.ip_address(f"{base}.{end_part}")
                else:
                    end_ip = ipaddress.ip_address(end_part)

                current = int(start_ip)
                end = int(end_ip)
                while current <= end:
                    ips.append(str(ipaddress.ip_address(current)))
                    current += 1
        else:
            # IP único
            ips.append(ip_range)

    return ips


def scan_network(ip_range: str, ports: list[int] = None,
                 timeout: float = 1.0, workers: int = 100) -> list[dict]:
    """Escaneia uma faixa de IPs procurando câmeras."""

    if ports is None:
        ports = list(CAMERA_PORTS.keys())

    ips = parse_ip_range(ip_range)
    total_scans = len(ips) * len(ports)

    print(f"Escaneando {len(ips)} IPs em {len(ports)} portas ({total_scans} verificações)")
    print(f"Portas: {', '.join(str(p) for p in ports)}")
    print("-" * 50)

    found_cameras = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}

        for ip in ips:
            for port in ports:
                future = executor.submit(check_port, ip, port, timeout)
                futures[future] = (ip, port)

        for future in as_completed(futures):
            completed += 1

            # Mostrar progresso
            if completed % 500 == 0 or completed == total_scans:
                pct = (completed / total_scans) * 100
                print(f"  Progresso: {completed}/{total_scans} ({pct:.1f}%)", end="\r")

            result = future.result()
            if result:
                ip, port, service = result
                if ip not in found_cameras:
                    found_cameras[ip] = []
                found_cameras[ip].append({"port": port, "service": service})
                print(f"\n  [+] ENCONTRADO: {ip}:{port} ({service})")

    print("\n")
    return found_cameras


def main():
    parser = argparse.ArgumentParser(
        description="Scanner de câmeras IP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 scan_cameras.py 192.168.1.0/24
  python3 scan_cameras.py 10.0.0.1-10.0.0.100
  python3 scan_cameras.py 192.168.0.0/24 -p 554 80
  python3 scan_cameras.py 172.16.0.0/16 -t 0.5 -w 200
        """
    )
    parser.add_argument("ip_range", help="Faixa de IPs (CIDR ou range)")
    parser.add_argument("-p", "--ports", nargs="+", type=int,
                        help="Portas específicas para escanear")
    parser.add_argument("-t", "--timeout", type=float, default=1.0,
                        help="Timeout por conexão (padrão: 1.0s)")
    parser.add_argument("-w", "--workers", type=int, default=100,
                        help="Threads simultâneas (padrão: 100)")

    args = parser.parse_args()

    print("=" * 50)
    print("    SCANNER DE CÂMERAS IP")
    print("=" * 50)
    print()

    cameras = scan_network(
        args.ip_range,
        ports=args.ports,
        timeout=args.timeout,
        workers=args.workers
    )

    if not cameras:
        print("Nenhuma câmera encontrada na faixa especificada.")
        print("\nDicas:")
        print("  - Verifique se a faixa de IP está correta")
        print("  - Aumente o timeout (-t 2.0)")
        print("  - Verifique se há firewall bloqueando")
        return 1

    print("=" * 50)
    print(f"RESUMO: {len(cameras)} dispositivo(s) encontrado(s)")
    print("=" * 50)

    for ip, ports_info in sorted(cameras.items()):
        print(f"\n{ip}:")
        for p in ports_info:
            print(f"  - Porta {p['port']}: {p['service']}")

        # Sugerir URL RTSP se porta 554 está aberta
        if any(p['port'] == 554 for p in ports_info):
            print(f"  RTSP: rtsp://usuario:senha@{ip}:554/stream")

    return 0


if __name__ == "__main__":
    sys.exit(main())
