import hashlib


def calculate_sha256(file_path) -> str | None:
    """Calculate SHA-256 hash of a file on disk. Returns hex string or None."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, IOError):
        return None


def calculate_sha256_bytes(data: bytes) -> str:
    """Calculate SHA-256 hash of a bytes object. Returns hex string."""
    return hashlib.sha256(data).hexdigest()
