import json
import os
from datetime import datetime, timezone

from flask import (
    Blueprint, redirect, url_for, render_template, jsonify,
    send_file, flash, current_app, Response,
)
from flask_login import current_user
from sqlalchemy import text

from app.models import Process, db
from app.version import APP_VERSION
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
        return render_template("dashboard.html", workload=None, bpmn_summaries=[])
    processes = Process.query.filter_by(account_id=account_id).order_by(Process.id).all()

    from app.services.bpmn_simulation import analyze_bpmn
    from app.services.workload_service import cross_process_workload

    # Strategische Engpass-Sicht: prozessübergreifende Personen-Auslastung aus dem
    # gespeicherten Mengengerüst (BPMN-Modell). Ohne Mengengerüst leer.
    volumes = {p.id: p.annual_cases for p in processes if (p.annual_cases or 0) > 0}
    workload = cross_process_workload(account_id, volumes) if volumes else None

    # BPMN-Kostenübersicht (Aufwand/Kosten je Prozess aus dem BPMN-Modell)
    bpmn_summaries = []
    for process in processes:
        a = analyze_bpmn(process)
        if a["has_model"]:
            bpmn_summaries.append({
                "process": process,
                "activity_count": len(a["activities"]),
                "total_effort": a["total_effort"], "expected_effort": a["expected_effort"],
                "total_cost": a["total_cost"], "expected_cost": a["expected_cost"],
            })

    return render_template("dashboard.html", workload=workload, bpmn_summaries=bpmn_summaries)
