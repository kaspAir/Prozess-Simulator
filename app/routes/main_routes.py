from flask import Blueprint, redirect, url_for, render_template, request, session
from flask_login import current_user

from app.models import Process
from app.dashboard import (
    dashboard_for_process,
    operational_dashboard_for_process,
    PERIOD_LABELS,
)
from app.auth.permissions import P_DASHBOARD_VIEW
from app.auth.service import require_permission, current_account_id

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return redirect(url_for("main.dashboard"))


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