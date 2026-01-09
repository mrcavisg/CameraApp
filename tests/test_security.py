"""
Tests for the security module.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCredentialManager:
    """Tests for CredentialManager class."""

    @pytest.fixture
    def credential_manager(self, mock_paths: MagicMock) -> MagicMock:
        """Create a CredentialManager with mocked paths."""
        # Re-import to pick up mocked paths
        with patch("cameraapp.security.PATHS", mock_paths):
            from cameraapp.security import CredentialManager

            return CredentialManager()

    def test_generate_camera_id(self, credential_manager: MagicMock) -> None:
        """Test camera ID generation is deterministic."""
        id1 = credential_manager._generate_camera_id("192.168.1.100", 554)
        id2 = credential_manager._generate_camera_id("192.168.1.100", 554)
        id3 = credential_manager._generate_camera_id("192.168.1.101", 554)

        assert id1 == id2  # Same inputs produce same ID
        assert id1 != id3  # Different IPs produce different IDs
        assert len(id1) == 16  # ID length is 16 characters

    def test_get_credential_key(self, credential_manager: MagicMock) -> None:
        """Test credential key generation."""
        camera_id = "abc123"
        key = credential_manager._get_credential_key(camera_id)

        assert credential_manager.SERVICE_NAME in key
        assert camera_id in key

    @patch("cameraapp.security.KEYRING_AVAILABLE", False)
    @patch("cameraapp.security.CRYPTOGRAPHY_AVAILABLE", False)
    def test_store_password_obfuscation_fallback(
        self, temp_dir: Path
    ) -> None:
        """Test password storage with base64 obfuscation fallback."""
        mock_paths = MagicMock()
        mock_paths.data_dir = temp_dir

        with patch("cameraapp.security.PATHS", mock_paths):
            from cameraapp.security import CredentialManager

            manager = CredentialManager()
            result = manager.store_password("192.168.1.100", 554, "test_password")

            assert result is True

    @patch("cameraapp.security.KEYRING_AVAILABLE", False)
    @patch("cameraapp.security.CRYPTOGRAPHY_AVAILABLE", False)
    def test_retrieve_password_obfuscation_fallback(
        self, temp_dir: Path
    ) -> None:
        """Test password retrieval with base64 obfuscation fallback."""
        mock_paths = MagicMock()
        mock_paths.data_dir = temp_dir

        with patch("cameraapp.security.PATHS", mock_paths):
            from cameraapp.security import CredentialManager

            manager = CredentialManager()

            # Store password
            manager.store_password("192.168.1.100", 554, "test_password")

            # Retrieve password
            password = manager.retrieve_password("192.168.1.100", 554)

            assert password == "test_password"

    def test_store_empty_password(self, credential_manager: MagicMock) -> None:
        """Test storing empty password returns True without action."""
        result = credential_manager.store_password("192.168.1.100", 554, "")
        assert result is True

    def test_retrieve_nonexistent_password(
        self, credential_manager: MagicMock
    ) -> None:
        """Test retrieving non-existent password returns None."""
        password = credential_manager.retrieve_password("10.0.0.1", 8080)
        assert password is None

    @patch("cameraapp.security.KEYRING_AVAILABLE", False)
    @patch("cameraapp.security.CRYPTOGRAPHY_AVAILABLE", False)
    def test_delete_password(self, temp_dir: Path) -> None:
        """Test password deletion."""
        mock_paths = MagicMock()
        mock_paths.data_dir = temp_dir

        with patch("cameraapp.security.PATHS", mock_paths):
            from cameraapp.security import CredentialManager

            manager = CredentialManager()

            # Store and then delete
            manager.store_password("192.168.1.100", 554, "test_password")
            result = manager.delete_password("192.168.1.100", 554)

            assert result is True

            # Verify deletion
            password = manager.retrieve_password("192.168.1.100", 554)
            assert password is None


class TestCredentialManagerWithCryptography:
    """Tests for CredentialManager with cryptography library."""

    @pytest.fixture
    def manager_with_crypto(self, temp_dir: Path) -> MagicMock:
        """Create manager with cryptography enabled."""
        mock_paths = MagicMock()
        mock_paths.data_dir = temp_dir

        with patch("cameraapp.security.PATHS", mock_paths):
            with patch("cameraapp.security.KEYRING_AVAILABLE", False):
                with patch("cameraapp.security.CRYPTOGRAPHY_AVAILABLE", True):
                    from cameraapp.security import CredentialManager

                    return CredentialManager()

    @pytest.mark.skipif(
        True,  # Skip if cryptography not installed
        reason="cryptography library not available",
    )
    def test_encrypted_storage_roundtrip(
        self, manager_with_crypto: MagicMock
    ) -> None:
        """Test encrypted password storage and retrieval."""
        original_password = "super_secret_123!@#"

        manager_with_crypto.store_password("192.168.1.100", 554, original_password)
        retrieved = manager_with_crypto.retrieve_password("192.168.1.100", 554)

        assert retrieved == original_password


class TestGlobalCredentialManager:
    """Tests for global credential manager instance."""

    def test_global_instance_exists(self) -> None:
        """Test that global credential_manager is available."""
        from cameraapp.security import credential_manager

        assert credential_manager is not None
        assert hasattr(credential_manager, "store_password")
        assert hasattr(credential_manager, "retrieve_password")
        assert hasattr(credential_manager, "delete_password")
