"""
Upload service — validates files and routes them to local storage or S3.

Returns a UploadResult namedtuple so callers always get a consistent interface
regardless of which storage backend was used.
"""

import os
import uuid
import logging
from collections import namedtuple
from werkzeug.utils import secure_filename
from flask import current_app
from services.integrity import calculate_sha256, calculate_sha256_bytes

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_MIMETYPES = {'image/jpeg', 'image/png', 'image/webp'}
MIME_CONTENT_TYPES = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'webp': 'image/webp',
}

# Returned by save_upload() regardless of storage backend
UploadResult = namedtuple('UploadResult', [
    'filename',      # local filename (None if stored in S3 only)
    's3_key',        # S3 object key (None if stored locally)
    'sha256_hash',   # hex SHA-256 of the file bytes
    'storage',       # 'local' or 's3'
])


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _detect_mime(header: bytes) -> str | None:
    if header[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if len(header) >= 12 and header[8:12] == b'WEBP':
        return 'image/webp'
    return None


def _validate(file) -> tuple[str, bytes]:
    """
    Validate extension and MIME header.
    Returns (ext, file_bytes) or raises ValueError.
    """
    if not file or not file.filename:
        raise ValueError('No file selected.')

    if not allowed_file(file.filename):
        raise ValueError('Only JPG, JPEG, PNG and WEBP files are allowed.')

    # Read all bytes once — needed for MIME check, SHA-256, and S3 upload
    file_bytes = file.read()

    if len(file_bytes) == 0:
        raise ValueError('Uploaded file is empty.')

    # Check actual file content, not just the extension
    mime = _detect_mime(file_bytes[:12])
    if mime and mime not in ALLOWED_MIMETYPES:
        raise ValueError('File content does not match an allowed image type.')

    ext = file.filename.rsplit('.', 1)[1].lower()
    return ext, file_bytes


def save_upload(file, item_type: str = 'LOST') -> UploadResult:
    """
    Validate and store an uploaded image.

    If S3 is configured  → upload to S3, return s3_key.
    If S3 not configured → save to local static/uploads/, return filename.

    Raises ValueError on validation failure.
    Raises RuntimeError on storage failure.
    """
    if not file or file.filename == '':
        return UploadResult(None, None, None, 'none')

    ext, file_bytes = _validate(file)

    # Import here to avoid circular imports at module load time
    from services.s3_service import is_s3_configured, upload_file, build_object_key

    if is_s3_configured():
        return _save_to_s3(file_bytes, ext, item_type)
    else:
        return _save_locally(file_bytes, ext)


def _save_to_s3(file_bytes: bytes, ext: str, item_type: str) -> UploadResult:
    from services.s3_service import upload_file, build_object_key

    # Build a fake original filename just to get the extension into build_object_key
    object_key = build_object_key(item_type, f'upload.{ext}')
    content_type = MIME_CONTENT_TYPES.get(ext, 'image/jpeg')

    s3_key, sha256_hex, error = upload_file(file_bytes, object_key, content_type)
    if error:
        raise RuntimeError(f'S3 upload failed: {error}')

    logger.info('File stored in S3: %s', s3_key)
    return UploadResult(filename=None, s3_key=s3_key, sha256_hash=sha256_hex, storage='s3')


def _save_locally(file_bytes: bytes, ext: str) -> UploadResult:
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    safe_name = secure_filename(unique_name)

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    save_path = os.path.join(upload_folder, safe_name)

    with open(save_path, 'wb') as f:
        f.write(file_bytes)

    sha256_hex = calculate_sha256(save_path)
    logger.info('File stored locally: %s (SHA-256: %s)', safe_name, sha256_hex)
    return UploadResult(filename=safe_name, s3_key=None, sha256_hash=sha256_hex, storage='local')
