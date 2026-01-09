# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-09

### Added
- Complete project restructure with professional standards
- Secure credential storage using keyring/cryptography
- Type hints throughout the codebase
- Comprehensive test suite with pytest
- CI/CD pipeline with GitHub Actions
- Pre-commit hooks for code quality
- Professional documentation (README, CHANGELOG, LICENSE)
- Cross-platform configuration with appdirs
- Dataclasses for configuration management
- Proper logging with rotation

### Changed
- Refactored all modules following PEP 8 guidelines
- Improved error handling and logging
- Enhanced camera reconnection logic
- Modernized project structure (src layout)
- Updated dependencies in pyproject.toml

### Security
- Passwords no longer stored in plain text JSON
- Added keyring integration for system credential storage
- Implemented file-based encryption fallback with PBKDF2
- Credential files have restricted permissions (600)
- Passwords masked in log output

### Removed
- Debug print statements
- Redundant code and comments
- Version folders (now using git tags)

## [0.2.3] - 2023-08-15

### Deprecated
- This version has been discontinued in favor of v1.0.0

## [0.2.2] - 2023-XX-XX

### Added
- Windows and Linux platform support
- Video format converter utilities

## [0.2.1] - 2023-XX-XX

### Changed
- Marked as stable version

## [0.2.0] - 2023-XX-XX

### Added
- ONVIF camera discovery
- RTSP direct connection support
- Multi-camera grid display
- Aspect ratio controls

## [0.1.0] - 2023-XX-XX

### Added
- Initial release
- Basic camera connection functionality
- Simple Tkinter GUI
