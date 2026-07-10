import json
import os
from datetime import datetime, timezone

from flask import (
    Blueprint, redirect, url_for, render_template, request, session, jsonify,
    send_file, flash, current_app, Response,
)
from flask_login import current_user
from sqlalchemy import text

from app.models import Process, db
from app.version import APP_VERSION
from app.dashboard import (
    dashboard_for_process,
    operational_dashboard_for_process,
    PERIOD_LABELS,
)
from app.auth.permissions import P_DASHBOARD_VIEW, P_ACCOUNT_MEMBERS
from app.auth.service import require_permission, current_account_id

main_bp = Blueprint("main", __name__)


def _protocol_dir():
    """Verzeichnis, in das der Deploy das Testprotokoll kopiert (App-Root/data)."""
    return os.environ.get("PROTOCOL_DIR") or os.path.join(
        os.path.dirname(current_app.root_path), "data")


@main_bp.route("/test-protocol.pdf")
@require_permission(P_ACCOUNT_MEMBERS)
def test_protocol_pdf():
    """Liefert das PDF-Testprotokoll des zuletzt auf diese Umgebung deployten Builds
    (vom Deploy nach data/ kopiert). Nur für Verwaltungsberechtigte."""
    path = os.path.join(_protocol_dir(), "test-protocol.pdf")
    if not os.path.isfile(path):
        flash("Es liegt noch kein Testprotokoll vor – es entsteht beim nächsten "
              "Deploy dieser Umgebung.", "error")
        return redirect(url_for("main.dashboard"))
    return send_file(path, mimetype="application/pdf", as_attachment=False,
                     download_name="Testprotokoll_Prozess-Simulator.pdf")


@main_bp.route("/export/model.json")
@require_permission(P_DASHBOARD_VIEW)
def export_model_json():
    """Exportiert das Modell (Organisation, Einheiten, Rollen, Funktionen, Personen,
    Prozesse mit Parametern) des aktiven Accounts als JSON-Datei."""
    from app.services.export_service import build_model_export
    data = build_model_export(current_account_id())
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(body, mimetype="application/json", headers={
        "Content-Disposition": "attachment; filename=digitwin-modell.json"})


@main_bp.route("/export/model.xml")
@require_permission(P_DASHBOARD_VIEW)
def export_model_xml():
    """Wie export_model_json, jedoch als XML-Datei."""
    from app.services.export_service import build_model_export, model_to_xml
    data = build_model_export(current_account_id())
    body = model_to_xml(data)
    return Response(body, mimetype="application/xml", headers={
        "Content-Disposition": "attachment; filename=digitwin-modell.xml"})


@main_bp.route("/")
def index():
    return redirect(url_for("main.dashboard"))


@main_bp.route("/health")
def health():
    """Nicht-destruktiver Health-Check (ohne Login): prüft App-Erreichbarkeit und
    DB-Verbindung. Basis für den Post-Deploy-Smoke-Check und späteres Monitoring.
    200 = ok, 503 = degraded (z. B. DB nicht erreichbar)."""
    db_ok = True
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    payload = {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "version": APP_VERSION,
        "commit": os.getenv("GIT_COMMIT"),
        "time": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(payload), (200 if db_ok else 503)


@main_bp.route("/appearance")
@require_permission(P_DASHBOARD_VIEW)
def appearance():
    """Vergleichsseite Erscheinungsbild: Standard + drei Styleguide-Varianten.
    Die Umschaltung selbst passiert clientseitig (localStorage), damit das Team
    ohne Server-Roundtrip live vergleichen kann."""
    return render_template("appearance.html")


@main_bp.route("/dashboard")
@require_permission(P_DASHBOARD_VIEW)
def dashboard():
    account_id = current_account_id()
    if account_id is None:
        if current_user.is_super_admin:
            return redirect(url_for("admin.accounts"))
        return render_template(
            "dashboard.html", dashboard_items=[], operational_items={},
            op_cases=80, op_period="day", op_period_label="Tag", active_tab="strategic",
        )
    processes = Process.query.filter_by(account_id=account_id).order_by(Process.id).all()

    active_tab = request.args.get("tab")
    if active_tab:
        session["dashboard_active_tab"] = active_tab
    else:
        active_tab = session.get("dashboard_active_tab", "strategic")

    op_cases_arg = request.args.get("op_cases", type=float)
    if op_cases_arg is not None:
        op_cases = op_cases_arg
        session["dashboard_op_cases"] = op_cases
    else:
        op_cases = session.get("dashboard_op_cases", 80)

    op_period_arg = request.args.get("op_period")
    if op_period_arg:
        op_period = op_period_arg
        session["dashboard_op_period"] = op_period
    else:
        op_period = session.get("dashboard_op_period", "day")

    op_period_label = PERIOD_LABELS.get(op_period, "Tag")

    dashboard_items = [
        dashboard_for_process(process)
        for process in processes
    ]

    operational_items = {
        process.id: operational_dashboard_for_process(process, op_cases, op_period)
        for process in processes
    }

    return render_template(
        "dashboard.html",
        dashboard_items=dashboard_items,
        operational_items=operational_items,
        op_cases=op_cases,
        op_period=op_period,
        op_period_label=op_period_label,
        active_tab=active_tab,
    )
