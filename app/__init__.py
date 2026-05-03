import os
from dotenv import load_dotenv
from flask import Flask

from app.models import db

from app.routes.main_routes import main_bp
from app.routes.organization_routes import organization_bp
from app.web.process_routes import process_bp


def create_app():
    load_dotenv()

    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/strafbefehl_lab",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from app.routes.main_routes import main_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(organization_bp)
    app.register_blueprint(process_bp)

    @app.context_processor
    def utility_processor():
        def endpoint_exists(endpoint):
            return endpoint in app.view_functions

        return dict(endpoint_exists=endpoint_exists)

    return app