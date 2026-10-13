"""
S3 Service — handles all AWS S3 operations.

Design decisions:
- All functions return (result, error_message) tuples so callers can handle
  failures gracefully without catching exceptions everywhere.
- S3 is optional: is_s3_configured() must return True before any upload is attempted.
- Bucket stays private. Images are served via presigned URLs (15-minute expiry).
- Server-side encryption AES256 is applied on every PutObject call.
- Object keys follow the pattern: lost-items/<uuid>.<ext> or found-items/<uuid>.<ext>
"""

import logging
import uuid
import boto3
from botocore.exceptions import (
    ClientError, NoCredentialsError, PartialCredentialsError, EndpointResolutionError
)
from flask import current_app
from services.integrity import calculate_sha256_bytes

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def is_s3_configured() -> bool:
    """Return True only when all four required S3 env vars are present."""
    cfg = current_app.config
    required = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION', 'S3_BUCKET_NAME']
    configured = all(cfg.get(k, '').strip() for k in required)
    if not configured:
        logger.info('S3 not configured — using local file storage fallback.')
    return configured


def _get_client():
    """Create and return a boto3 S3 client using app config."""
    cfg = current_app.config
    return boto3.client(
        's3',
        aws_access_key_id=cfg['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=cfg['AWS_SECRET_ACCESS_KEY'],
        region_name=cfg['AWS_REGION'],
    )


def _bucket() -> str:
    return current_app.config['S3_BUCKET_NAME']


# ---------------------------------------------------------------------------
# Object key builder
# ---------------------------------------------------------------------------

def build_object_key(item_type: str, original_filename: str) -> str:
    """
    Build a safe, unique S3 object key.
    item_type: 'LOST' or 'FOUND'
    Returns e.g. 'lost-items/3f8a1c2d4e5b6a7f.jpg'
    """
    ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else 'jpg'
    folder = 'lost-items' if item_type.upper() == 'LOST' else 'found-items'
    return f"{folder}/{uuid.uuid4().hex}.{ext}"


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_file(file_bytes: bytes, object_key: str, content_type: str = 'image/jpeg'):
    """
    Upload bytes to S3 with AES256 server-side encryption.

    Returns (object_key, sha256_hex, None) on success.
    Returns (None, None, error_message) on failure.
    """
    sha256_hex = calculate_sha256_bytes(file_bytes)
    try:
        client = _get_client()
        client.put_object(
            Bucket=_bucket(),
            Key=object_key,
            Body=file_bytes,
            ContentType=content_type,
            ServerSideEncryption='AES256',
        )
        logger.info('Uploaded %s to S3 bucket %s (SHA-256: %s)', object_key, _bucket(), sha256_hex)
        return object_key, sha256_hex, None

    except NoCredentialsError:
        msg = 'AWS credentials are missing or invalid.'
        logger.error(msg)
        return None, None, msg

    except PartialCredentialsError:
        msg = 'AWS credentials are incomplete.'
        logger.error(msg)
        return None, None, msg

    except ClientError as e:
        code = e.response['Error']['Code']
        msg = _friendly_client_error(code, 'upload')
        logger.error('S3 ClientError on upload (%s): %s', code, e)
        return None, None, msg

    except Exception as e:
        msg = 'Unexpected error during S3 upload.'
        logger.error('S3 upload unexpected error: %s', e)
        return None, None, msg


# ---------------------------------------------------------------------------
# Download (for integrity verification)
# ---------------------------------------------------------------------------

def download_file(object_key: str):
    """
    Download an object from S3 and return its bytes.

    Returns (bytes, None) on success.
    Returns (None, error_message) on failure.
    """
    try:
        client = _get_client()
        response = client.get_object(Bucket=_bucket(), Key=object_key)
        data = response['Body'].read()
        logger.info('Downloaded %s from S3 (%d bytes)', object_key, len(data))
        return data, None

    except ClientError as e:
        code = e.response['Error']['Code']
        if code == 'NoSuchKey':
            msg = 'File not found in S3 — it may have been deleted.'
        else:
            msg = _friendly_client_error(code, 'download')
        logger.error('S3 ClientError on download (%s): %s', code, e)
        return None, msg

    except (NoCredentialsError, PartialCredentialsError):
        msg = 'AWS credentials are missing or invalid.'
        logger.error(msg)
        return None, msg

    except Exception as e:
        msg = 'Unexpected error retrieving file from S3.'
        logger.error('S3 download unexpected error: %s', e)
        return None, msg


# ---------------------------------------------------------------------------
# Presigned URL (temporary authenticated access — never exposes credentials)
# ---------------------------------------------------------------------------

def generate_presigned_url(object_key: str, expiry_seconds: int = 900):
    """
    Generate a presigned URL giving temporary read access to a private S3 object.
    Default expiry: 15 minutes (900 seconds).

    Returns (url, None) on success.
    Returns (None, error_message) on failure.
    """
    try:
        client = _get_client()
        url = client.generate_presigned_url(
            'get_object',
            Params={'Bucket': _bucket(), 'Key': object_key},
            ExpiresIn=expiry_seconds,
        )
        return url, None

    except ClientError as e:
        code = e.response['Error']['Code']
        msg = _friendly_client_error(code, 'presign')
        logger.error('S3 presign error (%s): %s', code, e)
        return None, msg

    except Exception as e:
        msg = 'Could not generate image access URL.'
        logger.error('S3 presign unexpected error: %s', e)
        return None, msg


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_file(object_key: str):
    """
    Delete an object from S3.

    Returns (True, None) on success.
    Returns (False, error_message) on failure.
    """
    try:
        client = _get_client()
        client.delete_object(Bucket=_bucket(), Key=object_key)
        logger.info('Deleted %s from S3', object_key)
        return True, None

    except ClientError as e:
        code = e.response['Error']['Code']
        msg = _friendly_client_error(code, 'delete')
        logger.error('S3 ClientError on delete (%s): %s', code, e)
        return False, msg

    except (NoCredentialsError, PartialCredentialsError):
        msg = 'AWS credentials are missing or invalid.'
        logger.error(msg)
        return False, msg

    except Exception as e:
        msg = 'Unexpected error deleting file from S3.'
        logger.error('S3 delete unexpected error: %s', e)
        return False, msg


# ---------------------------------------------------------------------------
# Configuration check (used on startup / admin page)
# ---------------------------------------------------------------------------

def check_s3_connection():
    """
    Verify S3 connectivity by calling head_bucket on the configured bucket.

    Returns (True, None) if reachable.
    Returns (False, error_message) otherwise.
    """
    if not is_s3_configured():
        return False, 'S3 environment variables are not set.'
    try:
        client = _get_client()
        client.head_bucket(Bucket=_bucket())
        logger.info('S3 connection check passed for bucket: %s', _bucket())
        return True, None

    except ClientError as e:
        code = e.response['Error']['Code']
        if code == '403':
            msg = f'Access denied to bucket "{_bucket()}". Check IAM permissions.'
        elif code == '404':
            msg = f'Bucket "{_bucket()}" does not exist.'
        else:
            msg = _friendly_client_error(code, 'connection check')
        logger.error('S3 connection check failed (%s): %s', code, e)
        return False, msg

    except (NoCredentialsError, PartialCredentialsError):
        msg = 'AWS credentials are missing or invalid.'
        logger.error(msg)
        return False, msg

    except Exception as e:
        msg = 'Could not connect to S3.'
        logger.error('S3 connection check unexpected error: %s', e)
        return False, msg


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _friendly_client_error(code: str, operation: str) -> str:
    messages = {
        'AccessDenied':          'Access denied. Check IAM permissions for this bucket.',
        'NoSuchBucket':          'S3 bucket not found. Check S3_BUCKET_NAME.',
        'InvalidAccessKeyId':    'Invalid AWS Access Key ID.',
        'SignatureDoesNotMatch': 'Invalid AWS Secret Access Key.',
        'NoSuchKey':             'The requested file does not exist in S3.',
        'EntityTooLarge':        'File is too large for S3 upload.',
        '403':                   'Access denied to S3 bucket.',
        '404':                   'S3 bucket or object not found.',
    }
    return messages.get(code, f'S3 {operation} failed (code: {code}).')
