"""Private, encrypted file storage. Files are never served from a public path."""
import base64
import hashlib
import os
import uuid
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.config import settings

ALLOWED = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}
SIGNATURES = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n", "application/pdf": b"%PDF"}


class InvalidUpload(ValueError):
    pass


def _fernet() -> Fernet:
    key = settings.encryption_key or base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def _root() -> Path:
    root = Path(settings.storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def detect_type(filename: str, content: bytes) -> str:
    """Check extension AND file signature, so a renamed file is rejected."""
    mime = ALLOWED.get(os.path.splitext(filename)[1].lower())
    if not mime:
        raise InvalidUpload("Unsupported file type. Upload a JPG, PNG or PDF.")
    if not content:
        raise InvalidUpload("The file is empty.")
    if not content.startswith(SIGNATURES[mime]):
        raise InvalidUpload("The file contents do not match its type.")
    return mime


def save_encrypted(content: bytes) -> str:
    name = f"{uuid.uuid4().hex}.enc"
    path = _root() / name
    path.write_bytes(_fernet().encrypt(content))
    os.chmod(path, 0o600)
    return name


def read_decrypted(name: str) -> bytes:
    return _fernet().decrypt((_root() / name).read_bytes())


def delete_file(name: str) -> None:
    if name:
        (_root() / name).unlink(missing_ok=True)
