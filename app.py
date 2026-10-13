import os
import logging
from flask import Flask, render_template
from config import Config
from extensions import db, login_manager

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

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    with app.app_context():
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        # Log which backend is active (mask credentials)
        if 'postgresql' in db_url or 'postgres' in db_url:
            logger.info('Database backend: PostgreSQL')
        else:
            logger.info('Database backend: SQLite (local dev)')
        try:
            db.create_all()
        except Exception as exc:  # pragma: no cover
            logger.error('db.create_all() failed: %s', exc)
            raise

    return app


app = create_app()

if __name__ == '__main__':
    # debug=True only when run directly (local dev).
    # Gunicorn ignores this block entirely.
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug)
