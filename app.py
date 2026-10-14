import os
import logging
from flask import Flask, render_template
from config import Config
from extensions import db, login_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from models.user import User
    from models.item import Item, Match

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.items import items_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(items_bp)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Return the connection to the pool at the end of every request."""
        if exception:
            db.session.rollback()
        db.session.remove()
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error('500 error: %s', e, exc_info=True)
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.route('/healthz')
    def healthz():
        """
        Lightweight health-check endpoint used by Render and for manual
        verification.  Tests the actual database connection.
        Returns 200 JSON on success, 503 on DB failure.
        Never exposes credentials or connection strings.
        """
        from flask import jsonify
        try:
            db.session.execute(db.text('SELECT 1'))
            db_ok = True
            db_msg = 'ok'
        except Exception as exc:
            db_ok = False
            db_msg = type(exc).__name__
            logger.error('Health check DB failure: %s', exc)
        status = 200 if db_ok else 503
        return jsonify(database=db_msg, status='ok' if db_ok else 'error'), status

    @app.route('/debug-s3')
    def debug_s3():
        """
        Diagnostic endpoint — shows S3 configuration status without
        exposing credentials.  Remove or restrict after debugging.
        """
        from flask import jsonify
        from services.s3_service import is_s3_configured, check_s3_connection
        cfg = app.config
        bucket    = cfg.get('S3_BUCKET_NAME', '')
        region    = cfg.get('AWS_REGION', '')
        key_set   = bool(cfg.get('AWS_ACCESS_KEY_ID', '').strip())
        secret_set = bool(cfg.get('AWS_SECRET_ACCESS_KEY', '').strip())
        configured = is_s3_configured()
        reachable, conn_err = check_s3_connection() if configured else (False, 'not configured')
        return jsonify(
            s3_configured=configured,
            bucket_name=bucket or '(not set)',
            region=region or '(not set)',
            access_key_set=key_set,
            secret_key_set=secret_set,
            s3_reachable=reachable,
            s3_error=conn_err,
        ), 200

    with app.app_context():
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        if 'postgresql' in db_url or 'postgres' in db_url:
            logger.info('Database backend: PostgreSQL')
        else:
            logger.info('Database backend: SQLite (local dev)')

        try:
            db.create_all()
        except Exception as exc:  # pragma: no cover
            logger.error('db.create_all() failed: %s', exc)
            raise

        # CRITICAL: dispose the engine connection pool after create_all().
        #
        # Gunicorn pre-forks worker processes AFTER this module is imported.
        # Without dispose(), each worker inherits the parent's open SSL
        # socket to PostgreSQL.  Multiple workers then share the same
        # underlying TCP/SSL connection, which causes:
        #   - psycopg2.OperationalError: SSL error: decryption failed or
        #     bad record mac
        #   - psycopg2.OperationalError: SSL SYSCALL error: EOF detected
        #
        # dispose() closes all connections in the pool.  Each worker then
        # opens its own fresh connection on its first request, which is the
        # correct behaviour.
        #
        # This is safe: SQLAlchemy re-opens connections lazily on demand.
        # It does NOT drop tables or delete data.
        db.engine.dispose()
        logger.info('Connection pool disposed after create_all (pre-fork safety).')

    return app


app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug)
