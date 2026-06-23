import os
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, request
from flask_login import current_user

from app.models import db

from app.routes.main_routes import main_bp
from app.routes.organization_routes import organization_bp
from app.routes.process_routes import process_bp
from app.routes.auth_routes import auth_bp
from app.routes.admin_routes import admin_bp
from app.auth import login_manager


# Endpunkte, die ohne Login erreichbar sind
PUBLIC_ENDPOINTS = {"auth.login", "auth.accept_invite", "static"}


def create_app():
    load_dotenv()

    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    # Standard ist SQLite (kein DB-Server noetig). Fuer PostgreSQL einfach
    # DATABASE_URL setzen, z. B.
    # postgresql+psycopg2://user:pass@host:5432/prozess_simulator
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///prozess_simulator.db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(organization_bp)
    app.register_blueprint(process_bp)

    # Globale Login-Wall: alles ausser den PUBLIC_ENDPOINTS erfordert Anmeldung.
    @app.before_request
    def require_login():
        endpoint = request.endpoint
        if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
            return None
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        return None

    @app.context_processor
    def utility_processor():
        from app.auth.service import (
            user_has_permission, current_account, active_organization_id,
        )

        def endpoint_exists(endpoint):
            return endpoint in app.view_functions

        def current_user_can(permission_key, organization_id=None):
            return user_has_permission(current_user, permission_key, organization_id)

        return dict(
            endpoint_exists=endpoint_exists,
            current_user_can=current_user_can,
            current_account=current_account(),
            active_organization_id=active_organization_id(),
        )

    return app
