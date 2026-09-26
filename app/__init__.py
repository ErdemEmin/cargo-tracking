"""Uygulama fabrikası (application factory)."""
import os

from flask import Flask

from config import Config


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    # app katmanı
    from app import models, routes

    models.init_app(app)
    app.register_blueprint(routes.bp)

    # Tabloyu ilk açılışta oluştur (container'da migration adımı gerektirmesin)
    if not app.config.get("SKIP_DB_INIT"):
        parent = os.path.dirname(app.config["DB_PATH"])
        if parent:
            os.makedirs(parent, exist_ok=True)
        with app.app_context():
            models.init_db()

    return app
