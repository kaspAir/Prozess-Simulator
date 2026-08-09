from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from app.models import (
    db, Account, Organization, Membership, AccessRole, RoleAssignment, Invitation, User,
    LoginEvent,
)
from app.auth.permissions import P_ACCOUNT_MEMBERS, ACCOUNT_ADMIN_ROLE
from app.auth.service import (
    require_permission, current_account, set_active_account, set_active_organization, create_invitation,
    is_last_account_admin, set_password, user_has_permission,
    accessible_organizations, has_account_wide_access, seed_template_roles,
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


@admin_bp.route("/members/create", methods=["POST"])
@require_permission(P_ACCOUNT_MEMBERS)
def create_member():
    account = current_account()
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role_id = request.form.get("access_role_id", type=int)
    org_id = request.form.get("organization_id", type=int) or None
    if not email or not role_id:
        flash("E-Mail und Rolle sind erforderlich.", "error")
        return redirect(url_for("admin.members"))

    user = User.query.filter_by(email=email).first()
    created = user is None
    if created:
        if len(password) < 8:
            flash("Passwort muss mindestens 8 Zeichen haben.", "error")
            return redirect(url_for("admin.members"))
        user = User(name=name or email, email=email)
        set_password(user, password)
        db.session.add(user)
        db.session.flush()

    membership = Membership.query.filter_by(user_id=user.id, account_id=account.id).first()
    if membership is None:
        membership = Membership(user_id=user.id, account_id=account.id)
        db.session.add(membership)
        db.session.flush()
    if RoleAssignment.query.filter_by(
        membership_id=membership.id, access_role_id=role_id, organization_id=org_id
    ).first() is None:
        db.session.add(RoleAssignment(
            membership_id=membership.id, access_role_id=role_id, organization_id=org_id))
    db.session.commit()

    if created:
        flash(f"Mitglied {email} angelegt (Passwort dem Mitglied mitteilen).", "success")
    else:
        flash(f"Bestehender Benutzer {email} zum Account hinzugefügt (Passwort unverändert).", "success")
    return redirect(url_for("admin.members"))


@admin_bp.route("/members/<int:membership_id>/delete", methods=["POST"])
@require_permission(P_ACCOUNT_MEMBERS)
def delete_member(membership_id):
    """Entfernt ein Mitglied (samt Rollenzuweisungen) aus dem Mandanten. Der
    Benutzer selbst bleibt bestehen (kann in anderen Mandanten Mitglied sein)."""
    account = current_account()
    m = db.session.get(Membership, membership_id)
    if not m or m.account_id != account.id:
        abort(404)
    if is_last_account_admin(m):
        flash("Der letzte Account-Admin kann nicht entfernt werden.", "error")
        return redirect(url_for("admin.members"))
    if m.user_id == current_user.id:
        flash("Du kannst dich nicht selbst aus dem Mandanten entfernen.", "error")
        return redirect(url_for("admin.members"))
    email = m.user.email
    db.session.delete(m)   # RoleAssignments via cascade "all, delete-orphan"
    db.session.commit()
    flash(f"Mitglied {email} aus dem Mandanten entfernt.", "success")
    return redirect(url_for("admin.members"))


@admin_bp.route("/members/<int:membership_id>/reset-password", methods=["POST"])
@require_permission(P_ACCOUNT_MEMBERS)
def reset_password(membership_id):
    account = current_account()
    m = db.session.get(Membership, membership_id)
    if not m or m.account_id != account.id:
        abort(404)
    new_pw = request.form.get("password") or ""
    if len(new_pw) < 8:
        flash("Passwort muss mindestens 8 Zeichen haben.", "error")
        return redirect(url_for("admin.members"))
    set_password(m.user, new_pw)
    db.session.commit()
    flash(f"Passwort für {m.user.email} zurückgesetzt.", "success")
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
    org_id = request.form.get("organization_id", type=int) or None
    if org_id is None:
        # «ganzer Account» nur mit accountweitem Zugriff (sonst kein Account-Level)
        if not has_account_wide_access(current_user):
            abort(403)
    else:
        # Nur auf eine Organisation wechseln, die der Nutzer auch sehen darf.
        if org_id not in {o.id for o in accessible_organizations(current_user)}:
            abort(403)
    set_active_organization(org_id)
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


# ── Login-Protokoll ────────────────────────────────────────────────────────
@admin_bp.route("/logins")
@login_required
def logins():
    q = LoginEvent.query.order_by(LoginEvent.created_at.desc())
    if current_user.is_super_admin:
        events = q.limit(500).all()
    else:
        if not user_has_permission(current_user, P_ACCOUNT_MEMBERS):
            abort(403)
        account = current_account()
        member_ids = [m.user_id for m in Membership.query.filter_by(account_id=account.id).all()]
        events = q.filter(LoginEvent.user_id.in_(member_ids or [0])).limit(500).all()
    return render_template("admin/logins.html", events=events,
                           is_super=current_user.is_super_admin)


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


@admin_bp.route("/accounts/create", methods=["POST"])
@login_required
def create_account():
    """Legt einen neuen Mandanten (Account) an – inkl. Vorlagen-Rollen – und
    optional gleich einen Erst-Admin (Mandanten-Administrator). Nur Super-Admin.
    Das Organigramm erstellt später ein Benutzer des Mandanten selbst im Tool."""
    _super_admin_only()
    name = (request.form.get("name") or "").strip()
    admin_name = (request.form.get("admin_name") or "").strip()
    admin_email = (request.form.get("admin_email") or "").strip().lower()
    admin_password = request.form.get("admin_password") or ""
    if not name:
        flash("Name des Mandanten ist erforderlich.", "error")
        return redirect(url_for("admin.accounts"))
    if admin_email and len(admin_password) < 8:
        flash("Passwort des Erst-Admins muss mindestens 8 Zeichen haben.", "error")
        return redirect(url_for("admin.accounts"))

    acc = Account(name=name)
    db.session.add(acc)
    db.session.flush()
    seed_template_roles(acc.id)
    db.session.flush()

    if admin_email:
        user = User.query.filter_by(email=admin_email).first()
        if user is None:
            user = User(name=admin_name or admin_email, email=admin_email)
            set_password(user, admin_password)
            db.session.add(user)
            db.session.flush()
        m = Membership(user_id=user.id, account_id=acc.id)
        db.session.add(m)
        db.session.flush()
        admin_role = AccessRole.query.filter_by(account_id=acc.id, name=ACCOUNT_ADMIN_ROLE).first()
        db.session.add(RoleAssignment(membership_id=m.id, access_role_id=admin_role.id,
                                      organization_id=None))
    db.session.commit()
    msg = f"Mandant «{name}» angelegt."
    if admin_email:
        msg += f" Erst-Admin {admin_email} zugewiesen."
    flash(msg, "success")
    return redirect(url_for("admin.accounts"))
