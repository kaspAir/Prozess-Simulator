from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from app.models import (
    db, Account, Organization, Membership, AccessRole, RoleAssignment, Invitation,
)
from app.auth.permissions import P_ACCOUNT_MEMBERS, ALL_PERMISSIONS
from app.auth.service import (
    require_permission, current_account, current_account_id,
    set_active_account, set_active_organization, create_invitation,
    is_last_account_admin,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _super_admin_only():
    if not current_user.is_super_admin:
        abort(403)


# ── Mitglieder & Rollen (Account-Admin) ────────────────────────────────────
@admin_bp.route("/members")
@require_permission(P_ACCOUNT_MEMBERS)
def members():
    account = current_account()
    if account is None:
        flash("Kein aktiver Account.", "error")
        return redirect(url_for("admin.accounts"))
    memberships = Membership.query.filter_by(account_id=account.id).all()
    roles = AccessRole.query.filter_by(account_id=account.id).order_by(AccessRole.name).all()
    orgs = Organization.query.filter_by(account_id=account.id).order_by(Organization.name).all()
    invitations = Invitation.query.filter_by(account_id=account.id, status="pending").all()
    return render_template(
        "admin/members.html",
        account=account, memberships=memberships, roles=roles,
        orgs=orgs, invitations=invitations,
    )


@admin_bp.route("/invite", methods=["POST"])
@require_permission(P_ACCOUNT_MEMBERS)
def invite():
    account = current_account()
    email = (request.form.get("email") or "").strip().lower()
    role_id = request.form.get("access_role_id", type=int)
    org_id = request.form.get("organization_id", type=int) or None
    if not email or not role_id:
        flash("E-Mail und Rolle sind erforderlich.", "error")
        return redirect(url_for("admin.members"))
    inv = create_invitation(account.id, email, role_id, org_id)
    link = url_for("auth.accept_invite", token=inv.token, _external=True)
    flash(f"Einladung erstellt. Link zum Teilen: {link}", "success")
    return redirect(url_for("admin.members"))


@admin_bp.route("/assign", methods=["POST"])
@require_permission(P_ACCOUNT_MEMBERS)
def assign_role():
    account = current_account()
    membership_id = request.form.get("membership_id", type=int)
    role_id = request.form.get("access_role_id", type=int)
    org_id = request.form.get("organization_id", type=int) or None
    membership = db.session.get(Membership, membership_id)
    if not membership or membership.account_id != account.id:
        abort(404)
    exists = RoleAssignment.query.filter_by(
        membership_id=membership_id, access_role_id=role_id, organization_id=org_id
    ).first()
    if exists is None:
        db.session.add(RoleAssignment(
            membership_id=membership_id, access_role_id=role_id, organization_id=org_id))
        db.session.commit()
        flash("Rolle zugewiesen.", "success")
    return redirect(url_for("admin.members"))


@admin_bp.route("/unassign/<int:assignment_id>", methods=["POST"])
@require_permission(P_ACCOUNT_MEMBERS)
def unassign_role(assignment_id):
    account = current_account()
    asg = db.session.get(RoleAssignment, assignment_id)
    if not asg or asg.membership.account_id != account.id:
        abort(404)
    # "mindestens ein Account-Admin"-Regel
    if (asg.organization_id is None and P_ACCOUNT_MEMBERS in asg.access_role.permission_keys
            and is_last_account_admin(asg.membership)):
        flash("Der letzte Account-Admin kann nicht entfernt werden.", "error")
        return redirect(url_for("admin.members"))
    db.session.delete(asg)
    db.session.commit()
    flash("Zuweisung entfernt.", "success")
    return redirect(url_for("admin.members"))


@admin_bp.route("/organizations", methods=["POST"])
@require_permission(P_ACCOUNT_MEMBERS)
def create_organization():
    account = current_account()
    name = (request.form.get("name") or "").strip()
    if name:
        db.session.add(Organization(name=name, account_id=account.id))
        db.session.commit()
        flash("Organisation angelegt.", "success")
    return redirect(url_for("admin.members"))


# ── Kontext-Wechsel ────────────────────────────────────────────────────────
@admin_bp.route("/switch-org", methods=["POST"])
@login_required
def switch_org():
    set_active_organization(request.form.get("organization_id", type=int) or None)
    return redirect(request.referrer or url_for("main.dashboard"))


@admin_bp.route("/switch-account/<int:account_id>")
@login_required
def switch_account(account_id):
    # Nur Super-Admin oder Mitglied des Accounts
    if not current_user.is_super_admin:
        m = Membership.query.filter_by(user_id=current_user.id, account_id=account_id).first()
        if m is None:
            abort(403)
    set_active_account(account_id)
    return redirect(url_for("main.dashboard"))


# ── Super-Admin: Übersicht aller Accounts ──────────────────────────────────
@admin_bp.route("/accounts")
@login_required
def accounts():
    _super_admin_only()
    rows = []
    for acc in Account.query.order_by(Account.name).all():
        rows.append({
            "account": acc,
            "members": Membership.query.filter_by(account_id=acc.id).count(),
            "organizations": Organization.query.filter_by(account_id=acc.id).count(),
        })
    return render_template("admin/accounts.html", rows=rows)
