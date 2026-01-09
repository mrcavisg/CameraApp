"""
Security module for CameraApp.

Handles secure storage and retrieval of sensitive credentials.
Uses keyring for system-level secure storage with fallback encryption.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
from pathlib import Path
from typing import Optional

from cameraapp.config import APP_NAME, LOGGER_NAME, PATHS

logger = logging.getLogger(LOGGER_NAME)

# Try to import keyring for secure storage
try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning(
        "keyring not available. Using fallback encryption. "
        "Install keyring for better security: pip install keyring"
    )

# Try to import cryptography for fallback encryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning(
        "cryptography not available. Passwords will be obfuscated only. "
        "Install cryptography for better security: pip install cryptography"
    )


class CredentialManager:
    """
    Manages secure storage and retrieval of camera credentials.

    Uses a tiered approach:
    1. keyring (system-level secure storage) - preferred
    2. cryptography (file-based encryption) - fallback
    3. base64 obfuscation - last resort (not secure, but better than plaintext)
    """

    SERVICE_NAME = f"{APP_NAME}_credentials"
    KEY_FILE = PATHS.data_dir / ".keyfile"
    SALT_FILE = PATHS.data_dir / ".salt"

    def __init__(self) -> None:
        """Initialize the credential manager."""
        self._fernet: Optional[Fernet] = None
        if CRYPTOGRAPHY_AVAILABLE and not KEYRING_AVAILABLE:
            self._init_encryption()

    def _init_encryption(self) -> None:
        """Initialize file-based encryption using Fernet."""
        try:
            # Get or create salt
            if self.SALT_FILE.exists():
                salt = self.SALT_FILE.read_bytes()
            else:
                salt = secrets.token_bytes(16)
                self.SALT_FILE.write_bytes(salt)
                os.chmod(self.SALT_FILE, 0o600)

            # Get or create key derivation password
            if self.KEY_FILE.exists():
                key_password = self.KEY_FILE.read_bytes()
            else:
                key_password = secrets.token_bytes(32)
                self.KEY_FILE.write_bytes(key_password)
                os.chmod(self.KEY_FILE, 0o600)

            # Derive encryption key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(key_password))
            self._fernet = Fernet(key)
            logger.debug("File-based encryption initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            self._fernet = None

    def _get_credential_key(self, camera_id: str) -> str:
        """Generate a unique key for storing camera credentials."""
        return f"{self.SERVICE_NAME}:{camera_id}"

    def _generate_camera_id(self, ip: str, port: int) -> str:
        """Generate a unique identifier for a camera."""
        raw = f"{ip}:{port}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def store_password(self, ip: str, port: int, password: str) -> bool:
        """
        Store a password securely.

        Args:
            ip: Camera IP address
            port: Camera port
            password: Password to store

        Returns:
            True if storage was successful
        """
        if not password:
            return True

        camera_id = self._generate_camera_id(ip, port)
        credential_key = self._get_credential_key(camera_id)

        try:
            if KEYRING_AVAILABLE:
                keyring.set_password(self.SERVICE_NAME, credential_key, password)
                logger.debug(f"Password stored in keyring for {ip}:{port}")
                return True

            if self._fernet:
                encrypted = self._fernet.encrypt(password.encode())
                cred_file = PATHS.data_dir / f".cred_{camera_id}"
                cred_file.write_bytes(encrypted)
                os.chmod(cred_file, 0o600)
                logger.debug(f"Password stored with encryption for {ip}:{port}")
                return True

            # Fallback: base64 obfuscation (NOT SECURE - just prevents casual viewing)
            obfuscated = base64.b64encode(password.encode()).decode()
            cred_file = PATHS.data_dir / f".cred_{camera_id}"
            cred_file.write_text(obfuscated)
            os.chmod(cred_file, 0o600)
            logger.warning(
                f"Password stored with obfuscation only for {ip}:{port}. "
                "Install keyring or cryptography for better security."
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store password for {ip}:{port}: {e}")
            return False

    def retrieve_password(self, ip: str, port: int) -> Optional[str]:
        """
        Retrieve a stored password.

        Args:
            ip: Camera IP address
            port: Camera port

        Returns:
            The stored password or None if not found
        """
        camera_id = self._generate_camera_id(ip, port)
        credential_key = self._get_credential_key(camera_id)

        try:
            if KEYRING_AVAILABLE:
                password = keyring.get_password(self.SERVICE_NAME, credential_key)
                if password:
                    logger.debug(f"Password retrieved from keyring for {ip}:{port}")
                    return password

            cred_file = PATHS.data_dir / f".cred_{camera_id}"
            if cred_file.exists():
                data = cred_file.read_bytes()

                if self._fernet:
                    try:
                        password = self._fernet.decrypt(data).decode()
                        logger.debug(
                            f"Password retrieved with encryption for {ip}:{port}"
                        )
                        return password
                    except Exception:
                        pass

                # Try base64 obfuscation fallback
                try:
                    password = base64.b64decode(data).decode()
                    logger.debug(
                        f"Password retrieved with obfuscation for {ip}:{port}"
                    )
                    return password
                except Exception:
                    pass

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve password for {ip}:{port}: {e}")
            return None

    def delete_password(self, ip: str, port: int) -> bool:
        """
        Delete a stored password.

        Args:
            ip: Camera IP address
            port: Camera port

        Returns:
            True if deletion was successful
        """
        camera_id = self._generate_camera_id(ip, port)
        credential_key = self._get_credential_key(camera_id)

        try:
            if KEYRING_AVAILABLE:
                try:
                    keyring.delete_password(self.SERVICE_NAME, credential_key)
                except keyring.errors.PasswordDeleteError:
                    pass

            cred_file = PATHS.data_dir / f".cred_{camera_id}"
            if cred_file.exists():
                cred_file.unlink()

            logger.debug(f"Password deleted for {ip}:{port}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete password for {ip}:{port}: {e}")
            return False


# Global credential manager instance
credential_manager = CredentialManager()
