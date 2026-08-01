import os
import sqlite3

from dotenv import load_dotenv
from flask import Flask, redirect, url_for, request, render_template
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.models import db


# SQLite-Härtung: WAL erlaubt gleichzeitiges Lesen während eines Schreibers,
# busy_timeout lässt Schreiber warten statt sofort "database is locked" zu werfen.
# Greift nur für SQLite-Verbindungen (bei PostgreSQL wirkungslos/übersprungen).
@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

from app.routes.main_routes import main_bp
from app.routes.organization_routes import organization_bp
from app.routes.process_routes import process_bp
from app.routes.auth_routes import auth_bp
from app.routes.admin_routes import admin_bp
from app.auth import login_manager


# Endpunkte, die ohne Login erreichbar sind
PUBLIC_ENDPOINTS = {"auth.login", "auth.accept_invite", "static", "main.health"}


def create_app():
    load_dotenv()

    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    # Standard ist SQLite (kein DB-Server noetig). Fuer PostgreSQL einfach
    # DATABASE_URL setzen, z. B.
    # postgresql+psycopg2://user:pass@host:5432/prozess_simulator
    db_uri = os.getenv("DATABASE_URL", "sqlite:///prozess_simulator.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # B-09/B-07: MariaDB schliesst inaktive Verbindungen (wait_timeout). Ohne
    # pool_pre_ping liefert die naechste Anfrage nach kurzer Inaktivitaet einen
    # Fehler ("MySQL server has gone away"), der erst nach Reload verschwindet.
    # pool_pre_ping prueft die Verbindung vor Gebrauch, pool_recycle erneuert sie
    # vorsorglich. Fuer SQLite (Tests/lokal) nicht noetig.
    engine_options = {"pool_pre_ping": True}
    if not db_uri.startswith("sqlite"):
        engine_options["pool_recycle"] = 280
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

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

    # Freundliche 403-Seite statt der nackten Werkzeug-Meldung: Ein angemeldeter
    # Nutzer, dem (noch) keine Rolle zugewiesen ist, soll verstehen, was fehlt –
    # und nicht "Forbidden: You don't have the permission…" sehen.
    @app.errorhandler(403)
    def forbidden(_e):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        from app.auth.service import current_account, _membership
        acc = current_account()
        no_role = True
        if acc is not None:
            m = _membership(current_user, acc.id)
            no_role = not (m and m.assignments)
        if no_role:
            app.logger.warning("403 fuer angemeldeten Nutzer ohne wirksame Rolle: "
                               "user=%s account=%s path=%s",
                               getattr(current_user, "email", "?"),
                               acc.id if acc else None, request.path)
        return render_template(
            "errors/403.html",
            user_name=getattr(current_user, "name", None),
            account_name=acc.name if acc else None,
            no_role=no_role,
        ), 403

    return app
