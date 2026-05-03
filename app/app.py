
from flask import Flask
from app.models import db
from dotenv import load_dotenv
import os

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///prozess_simulator.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.organization_routes import organization_bp
    from app.routes.process_routes import process_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(organization_bp)
    app.register_blueprint(process_bp)

    def endpoint_exists(endpoint):
        return endpoint in app.view_functions

    app.jinja_env.globals["endpoint_exists"] = endpoint_exists

    return app
