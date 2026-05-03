
from flask import Blueprint, render_template, request
from app.models import Process
from app.dashboard import dashboard_for_process, operational_dashboard_for_process, PERIOD_LABELS

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
def dashboard():
    processes = Process.query.order_by(Process.id).all()

    active_tab = request.args.get("tab") or "strategic"
    op_cases = request.args.get("op_cases", type=float) or 80
    op_period = request.args.get("op_period") or "day"

    dashboard_items = [dashboard_for_process(p) for p in processes]
    operational_items = {
        p.id: operational_dashboard_for_process(p, op_cases, op_period)
        for p in processes
    }

    return render_template(
        "dashboard.html",
        dashboard_items=dashboard_items,
        operational_items=operational_items,
        op_cases=op_cases,
        op_period=op_period,
        op_period_label=PERIOD_LABELS.get(op_period, "Tag"),
        active_tab=active_tab,
    )
