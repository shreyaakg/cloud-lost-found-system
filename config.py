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

    Render injects DATABASE_URL as  postgres://...  (legacy scheme).
    SQLAlchemy 2.x dropped that alias, so we normalise to postgresql://.

    We then pin the dialect to postgresql+psycopg2:// so SQLAlchemy never
    probes for psycopg3 (which is not installed).

    Falls back to SQLite only for local development when DATABASE_URL is
    absent.  If DATABASE_URL is set but malformed we raise immediately so
    the worker fails fast with a clear log message rather than silently
    using SQLite in production.
    """
    url = os.environ.get('DATABASE_URL', '').strip()

    if not url:
        return 'sqlite:///lostfound.db'

    # Normalise legacy scheme supplied by Render / Heroku
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]

    # Pin dialect to psycopg2 — prevents SQLAlchemy 2.x probing for psycopg3
    if url.startswith('postgresql://') and '+' not in url.split('://')[0]:
        url = 'postgresql+psycopg2://' + url[len('postgresql://'):]

    if not url.startswith('postgresql+psycopg2://'):
        raise ValueError(
            'DATABASE_URL is set but does not look like a PostgreSQL URL. '
            'Check the Render environment variable.'
        )

    return url


def _is_postgres():
    uri = _database_uri()
    return uri.startswith('postgresql')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB hard limit enforced by Flask
    UPLOAD_FOLDER = _upload_folder()
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}

    # -----------------------------------------------------------------------
    # SQLAlchemy connection-pool options
    #
    # These are critical for Render PostgreSQL stability:
    #
    # pool_pre_ping=True
    #   Before handing a connection to a query, SQLAlchemy issues a cheap
    #   "SELECT 1".  If the connection is stale (SSL reset, idle timeout,
    #   server restart) it is discarded and a fresh one is opened.  This
    #   eliminates "SSL SYSCALL error: EOF detected" on the first query of
    #   a request.
    #
    # pool_recycle=300
    #   Render's managed PostgreSQL closes idle connections after ~5 minutes.
    #   Recycling every 300 s (5 min) ensures SQLAlchemy never hands out a
    #   connection that the server has already closed.
    #
    # pool_size=5, max_overflow=10
    #   Render's free-tier PostgreSQL allows 25 connections.  With 2 Gunicorn
    #   workers (see Procfile) this gives each worker up to 15 connections
    #   with headroom.  Adjust if you scale workers.
    #
    # connect_args sslmode=require
    #   Render PostgreSQL requires SSL.  Explicitly requiring it prevents the
    #   driver from negotiating a plaintext fallback that can cause the
    #   "decryption failed or bad record mac" SSL handshake error.
    # -----------------------------------------------------------------------
    if _is_postgres():
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 5,
            'max_overflow': 10,
            'connect_args': {
                'sslmode': 'require',
                'connect_timeout': 10,
            },
        }
    else:
        # SQLite (local dev) — no pool options needed
        SQLALCHEMY_ENGINE_OPTIONS = {}

    # AWS — all read from environment variables, never hard-coded
    AWS_ACCESS_KEY_ID     = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_REGION            = os.environ.get('AWS_REGION', 'us-east-1')
    # Accept either S3_BUCKET_NAME or the legacy AWS_S3_BUCKET env var name
    S3_BUCKET_NAME        = os.environ.get('S3_BUCKET_NAME') or os.environ.get('AWS_S3_BUCKET', '')
    AWS_S3_BUCKET         = S3_BUCKET_NAME  # kept for backward compatibility
