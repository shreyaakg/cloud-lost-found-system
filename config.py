import os
from dotenv import load_dotenv

load_dotenv()


def _upload_folder():
    """
    Local upload folder path.
    On Render (ephemeral filesystem) we use /tmp/uploads.
    When S3 is configured this folder is still used as a temp staging area
    but the final file lives in S3.
    """
    if os.environ.get('RENDER'):
        path = '/tmp/uploads'
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    os.makedirs(path, exist_ok=True)
    return path


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///lostfound.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB hard limit enforced by Flask
    UPLOAD_FOLDER = _upload_folder()
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}

    # AWS — all read from environment variables, never hard-coded
    AWS_ACCESS_KEY_ID     = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_REGION            = os.environ.get('AWS_REGION', 'us-east-1')
    S3_BUCKET_NAME        = os.environ.get('S3_BUCKET_NAME', '')

    # Legacy key kept for backward compatibility with render.yaml
    AWS_S3_BUCKET = os.environ.get('S3_BUCKET_NAME', os.environ.get('AWS_S3_BUCKET', ''))
