# CameraApp

[![CI](https://github.com/mrcavisg/CameraApp/actions/workflows/ci.yml/badge.svg)](https://github.com/mrcavisg/CameraApp/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Professional IP Camera Management System with ONVIF and RTSP support.

A desktop application for managing and monitoring IP cameras, featuring automatic camera discovery, multi-camera display, and secure credential storage.

## Features

- **Multi-Protocol Support**: Connect via ONVIF or direct RTSP URL
- **Automatic Discovery**: Find ONVIF cameras on your network automatically
- **Multi-Camera View**: Display multiple camera feeds in a grid layout
- **Secure Credential Storage**: Passwords encrypted using system keyring or file-based encryption
- **Aspect Ratio Control**: Switch between 4:3, 16:9, or fit-to-window modes
- **Auto-Reconnection**: Automatic reconnection with exponential backoff
- **Cross-Platform**: Works on Linux, Windows, and macOS
- **Threaded Capture**: Non-blocking video capture for smooth UI

## Screenshots

*Coming soon*

## Installation

### From PyPI (Recommended)

```bash
pip install cameraapp
```

### From Source

```bash
# Clone the repository
git clone https://github.com/mrcavisg/CameraApp.git
cd CameraApp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install in development mode
pip install -e ".[all]"
```

### Dependencies

**Required:**
- Python 3.10+
- OpenCV (opencv-python)
- Pillow
- NumPy
- appdirs

**Optional:**
- `onvif-zeep` + `WSDiscovery` - For ONVIF camera support
- `keyring` - For secure credential storage (system keyring)
- `cryptography` - For file-based encryption fallback

Install optional dependencies:

```bash
# For ONVIF support
pip install cameraapp[onvif]

# For enhanced security
pip install cameraapp[security]

# All optional features
pip install cameraapp[all]
```

## Quick Start

### Running the Application

```bash
# If installed via pip
cameraapp

# Or run directly
python -m cameraapp
```

### Adding a Camera

1. Open the application
2. Go to **Options** > **Manage Cameras**
3. Click **Add RTSP** or **Add ONVIF**
4. Enter connection details
5. Click **Save**

### RTSP URL Format

```
rtsp://username:password@ip_address:port/stream_path
```

Examples:
- `rtsp://admin:password@192.168.1.100:554/stream1`
- `rtsp://192.168.1.100/live/main`

### ONVIF Discovery

1. Open **Manage Cameras**
2. Click **Discover ONVIF**
3. Wait for discovery to complete
4. Select a discovered camera and click **Edit** to add credentials

## Configuration

Configuration files are stored in:

- **Linux**: `~/.local/share/CameraApp/`
- **Windows**: `%APPDATA%\CFATech\CameraApp\`
- **macOS**: `~/Library/Application Support/CameraApp/`

### Files

| File | Description |
|------|-------------|
| `cameras.json` | Camera configurations (without passwords) |
| `logs/cameraapp.log` | Application logs |
| `.cred_*` | Encrypted credential files |

## Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/mrcavisg/CameraApp.git
cd CameraApp

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src/cameraapp --cov-report=html

# Run specific test file
pytest tests/test_camera.py -v
```

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint
flake8 src/ tests/
ruff check src/ tests/

# Type check
mypy src/cameraapp
```

### Building

```bash
# Build package
python -m build

# Check package
twine check dist/*
```

## Project Structure

```
CameraApp/
├── src/
│   └── cameraapp/
│       ├── __init__.py      # Package initialization
│       ├── __main__.py      # Entry point for python -m
│       ├── main.py          # Application entry point
│       ├── app.py           # Main GUI application
│       ├── camera.py        # Camera connection handling
│       ├── config.py        # Configuration management
│       ├── security.py      # Credential encryption
│       └── utils.py         # Utility functions
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_camera.py       # Camera tests
│   ├── test_config.py       # Config tests
│   ├── test_security.py     # Security tests
│   └── test_utils.py        # Utility tests
├── .github/
│   └── workflows/
│       ├── ci.yml           # CI pipeline
│       └── release.yml      # Release automation
├── pyproject.toml           # Project configuration
├── README.md                # This file
└── LICENSE                  # MIT License
```

## Security

### Credential Storage

CameraApp uses a tiered approach for secure credential storage:

1. **System Keyring** (Preferred): Uses the operating system's secure credential storage
2. **File Encryption**: Falls back to AES encryption with PBKDF2 key derivation
3. **Obfuscation**: Base64 encoding as last resort (not recommended)

For best security, install the `keyring` package:

```bash
pip install keyring
```

### Security Best Practices

- Passwords are **never** stored in the JSON configuration file
- Each camera's credentials are stored separately
- Credential files have restricted permissions (600)
- Passwords are masked in log output

## Troubleshooting

### Camera Won't Connect

1. Verify the RTSP URL is correct
2. Check network connectivity to the camera
3. Ensure credentials are correct
4. Try adding `;transport=tcp` to the RTSP URL
5. Check the logs in `~/.local/share/CameraApp/logs/`

### ONVIF Discovery Not Working

1. Ensure the camera supports ONVIF
2. Check that multicast is enabled on your network
3. Verify firewall allows UDP port 3702
4. Install ONVIF dependencies: `pip install onvif-zeep WSDiscovery`

### High CPU Usage

- Reduce the number of simultaneous cameras
- Lower camera resolution if possible
- Increase `frame_update_interval` in config

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Run linters (`black`, `flake8`, `mypy`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Caio Vinicius** - [CFA TECH](https://github.com/mrcavisg)

## Acknowledgments

- [OpenCV](https://opencv.org/) for video processing
- [python-onvif-zeep](https://github.com/FalkTannworthe/python-onvif-zeep) for ONVIF support
- [Tkinter](https://docs.python.org/3/library/tkinter.html) for the GUI framework
