"""
Network scanner module for CameraApp.

Provides ONVIF discovery and RTSP port scanning to find cameras on the network.
Includes direct ONVIF probing for cameras with WS-Discovery disabled.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

from cameraapp.config import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

# Common camera ports
CAMERA_PORTS = {
    554: "RTSP",
    8554: "RTSP Alt",
    80: "HTTP/ONVIF",
    8080: "HTTP Alt",
    8000: "Hikvision",
    8899: "Intelbras",
    443: "HTTPS",
    37777: "Dahua",
    34567: "DVR Generic",
}

# Common RTSP URL patterns by manufacturer
RTSP_URL_PATTERNS = {
    "hikvision": [
        "/Streaming/Channels/101",
        "/Streaming/Channels/1",
        "/h264/ch1/main/av_stream",
    ],
    "dahua": [
        "/cam/realmonitor?channel=1&subtype=0",
        "/live",
    ],
    "generic": [
        "/stream1",
        "/live/main",
        "/video1",
        "/1",
        "/h264",
    ],
    "intelbras": [
        "/cam/realmonitor?channel=1&subtype=0",
        "/live/main",
    ],
    "onvif": [
        "/ch01.264",
        "/Streaming/Channels/101",
        "/stream1",
    ],
}

# ONVIF SOAP templates
ONVIF_DEVICE_INFO = '''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <GetDeviceInformation xmlns="http://www.onvif.org/ver10/device/wsdl"/>
  </s:Body>
</s:Envelope>'''

ONVIF_GET_PROFILES = '''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <GetProfiles xmlns="http://www.onvif.org/ver10/media/wsdl"/>
  </s:Body>
</s:Envelope>'''

ONVIF_GET_STREAM_URI = '''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <GetStreamUri xmlns="http://www.onvif.org/ver10/media/wsdl">
      <StreamSetup>
        <Stream xmlns="http://www.onvif.org/ver10/schema">RTP-Unicast</Stream>
        <Transport xmlns="http://www.onvif.org/ver10/schema">
          <Protocol>RTSP</Protocol>
        </Transport>
      </StreamSetup>
      <ProfileToken>{profile_token}</ProfileToken>
    </GetStreamUri>
  </s:Body>
</s:Envelope>'''


@dataclass
class ONVIFInfo:
    """Information retrieved from ONVIF device."""
    manufacturer: str = ""
    model: str = ""
    firmware: str = ""
    serial: str = ""
    hardware_id: str = ""
    profiles: list[str] = field(default_factory=list)
    rtsp_url: str = ""


@dataclass
class DiscoveredCamera:
    """Represents a discovered camera on the network."""

    ip: str
    ports: list[int] = field(default_factory=list)
    source: str = "scan"  # "onvif", "onvif_direct", or "scan"
    manufacturer: str = "Unknown"
    model: str = ""
    firmware: str = ""
    rtsp_urls: list[str] = field(default_factory=list)
    onvif_available: bool = False
    onvif_info: Optional[ONVIFInfo] = None

    def get_suggested_rtsp_url(self, username: str = "", password: str = "") -> str:
        """Get the most likely RTSP URL for this camera."""
        if not self.rtsp_urls:
            self._generate_rtsp_urls()

        if self.rtsp_urls:
            url = self.rtsp_urls[0]
            if username or password:
                # Insert credentials into URL
                if "://" in url:
                    scheme, rest = url.split("://", 1)
                    if "@" in rest:
                        # Already has credentials, replace them
                        rest = rest.split("@", 1)[1]
                    return f"{scheme}://{username}:{password}@{rest}"
            return url
        return ""

    def _generate_rtsp_urls(self) -> None:
        """Generate possible RTSP URLs based on detected manufacturer."""
        # If we have ONVIF-discovered URL, use it first
        if self.onvif_info and self.onvif_info.rtsp_url:
            self.rtsp_urls = [self.onvif_info.rtsp_url]
            # Also add generic patterns as fallback
            base = f"rtsp://{self.ip}"
            port = 554 if 554 in self.ports else 554
            if port != 554:
                base = f"rtsp://{self.ip}:{port}"
            for pattern in RTSP_URL_PATTERNS["generic"][:2]:
                url = f"{base}{pattern}"
                if url not in self.rtsp_urls:
                    self.rtsp_urls.append(url)
            return

        base = f"rtsp://{self.ip}"
        port = 554 if 554 in self.ports else (8554 if 8554 in self.ports else 554)

        if port != 554:
            base = f"rtsp://{self.ip}:{port}"

        # Determine manufacturer from ports or ONVIF info
        if self.onvif_available and not self.manufacturer:
            self.manufacturer = "ONVIF"
            patterns = RTSP_URL_PATTERNS["onvif"]
        elif 8000 in self.ports:
            self.manufacturer = "Hikvision"
            patterns = RTSP_URL_PATTERNS["hikvision"]
        elif 37777 in self.ports:
            self.manufacturer = "Dahua"
            patterns = RTSP_URL_PATTERNS["dahua"]
        elif 8899 in self.ports:
            self.manufacturer = "Intelbras"
            patterns = RTSP_URL_PATTERNS["intelbras"]
        else:
            patterns = RTSP_URL_PATTERNS["generic"]

        self.rtsp_urls = [f"{base}{pattern}" for pattern in patterns]


class ONVIFProber:
    """
    Probes cameras directly via ONVIF HTTP/SOAP.
    Works even when WS-Discovery is disabled.
    """

    ONVIF_PATHS = [
        "/onvif/device_service",
        "/onvif/device",
        "/onvif",
    ]

    MEDIA_PATHS = [
        "/onvif/media_service",
        "/onvif/media",
        "/onvif/Media",
    ]

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout

    def probe(self, ip: str, port: int = 80) -> Optional[ONVIFInfo]:
        """
        Probe a device for ONVIF support via direct HTTP.

        Args:
            ip: Device IP address
            port: HTTP port (default 80)

        Returns:
            ONVIFInfo if ONVIF is available, None otherwise
        """
        # Try to get device info
        for path in self.ONVIF_PATHS:
            url = f"http://{ip}:{port}{path}"
            response = self._soap_request(url, ONVIF_DEVICE_INFO)
            if response and "GetDeviceInformationResponse" in response:
                info = self._parse_device_info(response)

                # Try to get RTSP URL
                rtsp_url = self._get_rtsp_url(ip, port)
                if rtsp_url:
                    info.rtsp_url = rtsp_url

                logger.info(f"ONVIF direct probe success: {ip}:{port}")
                return info

        return None

    def _soap_request(self, url: str, body: str) -> Optional[str]:
        """Send SOAP request and return response."""
        try:
            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "User-Agent": "CameraApp/1.0",
            }
            req = urllib.request.Request(
                url,
                data=body.encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout):
            return None
        except Exception as e:
            logger.debug(f"SOAP request error to {url}: {e}")
            return None

    def _parse_device_info(self, response: str) -> ONVIFInfo:
        """Parse ONVIF GetDeviceInformationResponse."""
        info = ONVIFInfo()

        # Extract fields using regex (simple parsing)
        patterns = {
            "manufacturer": r"<tds:Manufacturer>([^<]*)</tds:Manufacturer>",
            "model": r"<tds:Model>([^<]*)</tds:Model>",
            "firmware": r"<tds:FirmwareVersion>([^<]*)</tds:FirmwareVersion>",
            "serial": r"<tds:SerialNumber>([^<]*)</tds:SerialNumber>",
            "hardware_id": r"<tds:HardwareId>([^<]*)</tds:HardwareId>",
        }

        for field_name, pattern in patterns.items():
            match = re.search(pattern, response)
            if match:
                setattr(info, field_name, match.group(1))

        return info

    def _get_rtsp_url(self, ip: str, port: int = 80) -> Optional[str]:
        """Get RTSP URL via ONVIF media service."""
        # First get profiles
        for media_path in self.MEDIA_PATHS:
            url = f"http://{ip}:{port}{media_path}"
            response = self._soap_request(url, ONVIF_GET_PROFILES)
            if response and "Profiles" in response:
                # Extract first profile token
                match = re.search(r'token="([^"]+)"', response)
                if not match:
                    match = re.search(r"<tt:Name>([^<]+)</tt:Name>", response)

                if match:
                    profile_token = match.group(1)

                    # Get stream URI
                    stream_request = ONVIF_GET_STREAM_URI.format(
                        profile_token=profile_token
                    )
                    stream_response = self._soap_request(url, stream_request)

                    if stream_response:
                        uri_match = re.search(
                            r"<tt:Uri>([^<]+)</tt:Uri>",
                            stream_response
                        )
                        if uri_match:
                            return uri_match.group(1)

        return None


class NetworkScanner:
    """
    Scans network for IP cameras using ONVIF discovery, direct ONVIF probing,
    and port scanning.
    """

    def __init__(
        self,
        timeout: float = 1.0,
        max_workers: int = 100,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> None:
        """
        Initialize the network scanner.

        Args:
            timeout: Connection timeout in seconds
            max_workers: Maximum concurrent threads
            progress_callback: Optional callback(current, total, message)
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self._stop_requested = False
        self._onvif_prober = ONVIFProber(timeout=3.0)

    def stop(self) -> None:
        """Request the scanner to stop."""
        self._stop_requested = True

    def _report_progress(self, current: int, total: int, message: str = "") -> None:
        """Report progress to callback if set."""
        if self.progress_callback:
            try:
                self.progress_callback(current, total, message)
            except Exception:
                pass

    def discover_onvif(self, timeout: int = 10) -> list[DiscoveredCamera]:
        """
        Discover cameras using ONVIF WS-Discovery.

        Args:
            timeout: Discovery timeout in seconds

        Returns:
            List of discovered cameras
        """
        try:
            from wsdiscovery import WSDiscovery
        except ImportError:
            logger.warning("WSDiscovery not installed. ONVIF discovery unavailable.")
            return []

        logger.info("Starting ONVIF WS-Discovery...")
        self._report_progress(0, 1, "Buscando câmeras ONVIF (WS-Discovery)...")

        cameras = []
        wsd = None

        try:
            wsd = WSDiscovery()
            wsd.start()

            # ONVIF type filter
            class ONVIFType:
                namespace = "http://www.onvif.org/ver10/network/wsdl"
                local_part = "NetworkVideoTransmitter"

                def getNamespace(self):
                    return self.namespace

                def getLocalname(self):
                    return self.local_part

                def getNamespacePrefix(self):
                    return None

                def getFullname(self):
                    return f"{{{self.namespace}}}{self.local_part}"

            services = wsd.searchServices(types=[ONVIFType()], timeout=timeout)
            existing_ips = set()

            for service in services:
                if self._stop_requested:
                    break

                ip = self._extract_ip_from_service(service)
                if ip and ip not in existing_ips:
                    existing_ips.add(ip)
                    camera = DiscoveredCamera(
                        ip=ip,
                        ports=[80, 554],
                        source="onvif",
                        onvif_available=True,
                    )
                    cameras.append(camera)
                    logger.info(f"ONVIF WS-Discovery found: {ip}")

            wsd.stop()

        except Exception as e:
            logger.error(f"ONVIF WS-Discovery error: {e}")
            if wsd:
                try:
                    wsd.stop()
                except Exception:
                    pass

        self._report_progress(1, 1, f"WS-Discovery: {len(cameras)} câmera(s)")
        return cameras

    def _extract_ip_from_service(self, service) -> Optional[str]:
        """Extract IP address from WS-Discovery service."""
        ip = None

        try:
            xaddrs = service.getXAddrs()
            if xaddrs:
                for xaddr in xaddrs:
                    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", xaddr)
                    if match:
                        potential_ip = match.group(1)
                        if potential_ip != "127.0.0.1":
                            ip = potential_ip
                            break

            if not ip:
                epr = service.getEPR()
                match = re.search(r"(\d+\.\d+\.\d+\.\d+)", epr)
                if match:
                    ip = match.group(1)
        except Exception:
            pass

        return ip

    def probe_onvif_direct(self, ip: str, port: int = 80) -> Optional[DiscoveredCamera]:
        """
        Probe a specific IP for ONVIF via direct HTTP (no WS-Discovery).

        Args:
            ip: IP address to probe
            port: HTTP port (default 80)

        Returns:
            DiscoveredCamera if ONVIF found, None otherwise
        """
        info = self._onvif_prober.probe(ip, port)
        if info:
            camera = DiscoveredCamera(
                ip=ip,
                ports=[port, 554],
                source="onvif_direct",
                manufacturer=info.manufacturer or info.hardware_id or "ONVIF",
                model=info.model,
                firmware=info.firmware,
                onvif_available=True,
                onvif_info=info,
            )
            if info.rtsp_url:
                camera.rtsp_urls = [info.rtsp_url]
            return camera
        return None

    def scan_ports(
        self,
        ip_range: str,
        ports: Optional[list[int]] = None,
        probe_onvif: bool = True,
    ) -> list[DiscoveredCamera]:
        """
        Scan a range of IPs for camera ports.

        Args:
            ip_range: IP range in CIDR notation (e.g., "192.168.0.0/24")
            ports: List of ports to scan (default: common camera ports)
            probe_onvif: Whether to probe ONVIF on port 80 (default True)

        Returns:
            List of discovered cameras
        """
        if ports is None:
            ports = list(CAMERA_PORTS.keys())

        ips = self._parse_ip_range(ip_range)
        total_scans = len(ips) * len(ports)

        logger.info(f"Scanning {len(ips)} IPs on {len(ports)} ports")
        self._report_progress(0, total_scans, f"Escaneando {len(ips)} IPs...")

        found_cameras: dict[str, DiscoveredCamera] = {}
        ips_with_port_80: list[str] = []
        completed = 0

        # Phase 1: Port scan
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            for ip in ips:
                if self._stop_requested:
                    break
                for port in ports:
                    future = executor.submit(self._check_port, ip, port)
                    futures[future] = (ip, port)

            for future in as_completed(futures):
                if self._stop_requested:
                    break

                completed += 1
                if completed % 100 == 0 or completed == total_scans:
                    self._report_progress(
                        completed, total_scans,
                        f"Escaneando portas... {completed}/{total_scans}"
                    )

                result = future.result()
                if result:
                    ip, port = result
                    if ip not in found_cameras:
                        found_cameras[ip] = DiscoveredCamera(
                            ip=ip,
                            ports=[],
                            source="scan",
                        )
                    found_cameras[ip].ports.append(port)
                    logger.info(f"Found open port: {ip}:{port}")

                    # Track IPs with port 80 for ONVIF probing
                    if port == 80 and ip not in ips_with_port_80:
                        ips_with_port_80.append(ip)

        # Phase 2: ONVIF direct probe on devices with port 80
        if probe_onvif and ips_with_port_80 and not self._stop_requested:
            self._report_progress(
                0, len(ips_with_port_80),
                f"Verificando ONVIF em {len(ips_with_port_80)} dispositivos..."
            )

            for i, ip in enumerate(ips_with_port_80):
                if self._stop_requested:
                    break

                self._report_progress(
                    i + 1, len(ips_with_port_80),
                    f"Verificando ONVIF: {ip} ({i+1}/{len(ips_with_port_80)})"
                )

                onvif_camera = self.probe_onvif_direct(ip)
                if onvif_camera:
                    # Update existing camera with ONVIF info
                    if ip in found_cameras:
                        cam = found_cameras[ip]
                        cam.onvif_available = True
                        cam.onvif_info = onvif_camera.onvif_info
                        cam.source = "onvif_direct"
                        cam.manufacturer = onvif_camera.manufacturer or cam.manufacturer
                        cam.model = onvif_camera.model
                        cam.firmware = onvif_camera.firmware
                        if onvif_camera.rtsp_urls:
                            cam.rtsp_urls = onvif_camera.rtsp_urls
                        # Add port 554 if not present
                        if 554 not in cam.ports:
                            cam.ports.append(554)
                    else:
                        found_cameras[ip] = onvif_camera

        # Generate RTSP URLs for cameras without ONVIF
        cameras = list(found_cameras.values())
        for camera in cameras:
            if not camera.rtsp_urls:
                camera._generate_rtsp_urls()

        self._report_progress(
            total_scans, total_scans,
            f"Scan completo: {len(cameras)} dispositivo(s)"
        )

        return cameras

    def _check_port(self, ip: str, port: int) -> Optional[tuple[str, int]]:
        """Check if a port is open on an IP."""
        if self._stop_requested:
            return None

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                return (ip, port)
        except Exception:
            pass
        return None

    def _parse_ip_range(self, ip_range: str) -> list[str]:
        """Parse an IP range string to list of IPs."""
        ips = []

        try:
            # Try CIDR notation
            network = ipaddress.ip_network(ip_range, strict=False)
            for ip in network.hosts():
                ips.append(str(ip))
        except ValueError:
            # Try range notation (e.g., 192.168.1.1-254)
            if "-" in ip_range:
                parts = ip_range.split("-")
                if len(parts) == 2:
                    try:
                        start_ip = ipaddress.ip_address(parts[0].strip())
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
                    except ValueError:
                        pass
            else:
                # Single IP
                try:
                    ipaddress.ip_address(ip_range)
                    ips.append(ip_range)
                except ValueError:
                    pass

        return ips

    def full_scan(
        self,
        ip_range: Optional[str] = None,
        include_onvif: bool = True,
        ports: Optional[list[int]] = None,
        probe_onvif_direct: bool = True,
    ) -> list[DiscoveredCamera]:
        """
        Perform a full network scan combining ONVIF discovery, direct probing,
        and port scanning.

        Args:
            ip_range: IP range for port scan (auto-detect if None)
            include_onvif: Whether to include ONVIF WS-Discovery
            ports: Ports to scan (default: common camera ports)
            probe_onvif_direct: Whether to probe ONVIF directly on port 80

        Returns:
            Combined list of discovered cameras (deduplicated)
        """
        self._stop_requested = False
        all_cameras: dict[str, DiscoveredCamera] = {}

        # ONVIF WS-Discovery (for cameras that support it)
        if include_onvif:
            onvif_cameras = self.discover_onvif()
            for cam in onvif_cameras:
                all_cameras[cam.ip] = cam

        # Port scan + direct ONVIF probe
        if ip_range:
            scanned_cameras = self.scan_ports(
                ip_range, ports, probe_onvif=probe_onvif_direct
            )
            for cam in scanned_cameras:
                if cam.ip in all_cameras:
                    # Merge information
                    existing = all_cameras[cam.ip]
                    for port in cam.ports:
                        if port not in existing.ports:
                            existing.ports.append(port)

                    # Update with ONVIF info if found
                    if cam.onvif_info and not existing.onvif_info:
                        existing.onvif_info = cam.onvif_info
                        existing.onvif_available = True
                        if cam.rtsp_urls:
                            existing.rtsp_urls = cam.rtsp_urls
                        if cam.manufacturer != "Unknown":
                            existing.manufacturer = cam.manufacturer

                    existing._generate_rtsp_urls()
                else:
                    all_cameras[cam.ip] = cam

        return list(all_cameras.values())


def get_local_network() -> Optional[str]:
    """Get the local network in CIDR notation."""
    try:
        # Get local IP by connecting to external address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()

        # Assume /24 network
        parts = local_ip.split(".")
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    except Exception:
        return None


def test_rtsp_url(url: str, timeout: float = 5.0) -> bool:
    """
    Test if an RTSP URL is accessible.

    Args:
        url: RTSP URL to test
        timeout: Connection timeout

    Returns:
        True if URL responds
    """
    try:
        import cv2

        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout * 1000))

        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            return ret

        cap.release()
        return False
    except Exception:
        return False
