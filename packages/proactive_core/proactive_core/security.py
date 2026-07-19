"""Encryption helpers for provider credentials and MFA secrets."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class CredentialCipher:
    """Authenticated encryption with a deployment-supplied root secret."""

    def __init__(self, root_secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(root_secret.encode()).digest())
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt one credential for database storage."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt one credential and reject modified ciphertext."""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Encrypted credential failed authentication") from exc
