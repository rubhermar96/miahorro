"""Encryption of sensitive columns (RNF-05), with a key derived from MIAHORRO_SECRET_KEY."""

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def _derive(secret_key: str, purpose: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=purpose).derive(
        secret_key.encode()
    )


def encrypt(secret_key: str, plaintext: str) -> str:
    fernet = Fernet(base64.urlsafe_b64encode(_derive(secret_key, b"miahorro:field-encryption")))
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(secret_key: str, token: str) -> str:
    fernet = Fernet(base64.urlsafe_b64encode(_derive(secret_key, b"miahorro:field-encryption")))
    return fernet.decrypt(token.encode()).decode()


def keyed_hash(secret_key: str, value: str) -> str:
    """HMAC-SHA256 for high-entropy secrets we only need to compare (recovery codes)."""
    key = _derive(secret_key, b"miahorro:keyed-hash")
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
