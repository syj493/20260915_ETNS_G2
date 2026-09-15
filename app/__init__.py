import os

from flask import Flask

from config import Config
from app.extensions import csrf, db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = None
    csrf.init_app(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.issues import issues_bp
    from app.routes.customers import customers_bp
    from app.routes.moving_cases import moving_cases_bp
    from app.routes.vendors import vendors_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(issues_bp, url_prefix="/issues")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(moving_cases_bp, url_prefix="/moving-cases")
    app.register_blueprint(vendors_bp, url_prefix="/vendors")
    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()

    return app
