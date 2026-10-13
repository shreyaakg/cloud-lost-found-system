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


def _database_uri():
    """
    Return the correct SQLAlchemy database URI.

    Render / Heroku supply  postgres://...  but SQLAlchemy 1.4+ dropped that
    scheme alias.  We normalise it to  postgresql://  first.

    SQLAlchemy 2.x with a bare  postgresql://  URL probes for psycopg3
    (import name 'psycopg') before falling back to psycopg2.  On Render that
    probe raises  ModuleNotFoundError: No module named 'psycopg'  and the
    worker crashes before it ever tries psycopg2-binary.

    Using the explicit dialect  postgresql+psycopg2://  bypasses the probe
    entirely and goes straight to psycopg2, which is what we ship.

    Falls back to SQLite for local development when DATABASE_URL is not set.
    """
    url = os.environ.get('DATABASE_URL', '')
    # Step 1 — fix legacy scheme
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    # Step 2 — pin the dialect to psycopg2 so SQLAlchemy 2.x never probes psycopg3
    if url.startswith('postgresql://') and '+' not in url.split('://')[0]:
        url = 'postgresql+psycopg2://' + url[len('postgresql://'):]
    return url or 'sqlite:///lostfound.db'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = _database_uri()
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
