"""Auth-/Berechtigungs-Helfer: aktiver Account/Organisation, Permission-Checks,
Decorator, Einladungen."""
import secrets
from functools import wraps

from flask import session, abort, has_request_context, request
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import (
    db, User, Account, Membership, RoleAssignment, Invitation,
)
from app.auth.permissions import P_ACCOUNT_MEMBERS


# ── Aktiver Kontext (Session) ──────────────────────────────────────────────
def current_account():
    aid = session.get("active_account_id") if has_request_context() else None
    authed = bool(current_user and current_user.is_authenticated)
    # Einen Session-Account NUR akzeptieren, wenn der angemeldete Nutzer dort auch
    # Mitglied ist (oder Super-Admin). Sonst koennte ein veralteter/fremder Wert
    # den Namen eines anderen Mandanten preisgeben.
    if aid and authed:
        if getattr(current_user, "is_super_admin", False) or \
                Membership.query.filter_by(user_id=current_user.id, account_id=aid).first():
            acc = db.session.get(Account, aid)
            if acc:
                return acc
    if authed:
        m = Membership.query.filter_by(user_id=current_user.id).first()
        if m:
            session["active_account_id"] = m.account_id
            return m.account
    return None


def seed_template_roles(account_id):
    """Legt die Vorlagen-Rollen (Account-Admin, Viewer, …) für einen neuen Account
    (Mandanten) an – analog zum Seed-Skript, aber zur Laufzeit."""
    from app.auth.permissions import TEMPLATE_ROLES
    from app.models import AccessRole, AccessRolePermission
    for name, perms in TEMPLATE_ROLES.items():
        if AccessRole.query.filter_by(account_id=account_id, name=name).first() is None:
            role = AccessRole(account_id=account_id, name=name, is_template=True)
            db.session.add(role)
            db.session.flush()
            for p in perms:
                db.session.add(AccessRolePermission(access_role_id=role.id, permission_key=p))


def has_account_wide_access(user, account=None):
    """True, wenn der User den ganzen Account sehen darf (Super-Admin oder eine
    accountweite Rollenzuweisung). Nur dann ist «ganzer Account» zulaessig."""
    if getattr(user, "is_super_admin", False):
        return True
    account = account or current_account()
    if account is None:
        return False
    m = _membership(user, account.id)
    return bool(m and any(a.organization_id is None for a in m.assignments))


def accessible_organizations(user, account=None):
    """Die Organisationen, die der User im Account sehen/wechseln darf. Super-Admin
    und accountweite Rollen sehen alle; sonst NUR die per-Organisation zugewiesenen.
    Andere Mandanten (Organisationen) existieren aus seiner Sicht schlicht nicht."""
    account = account or current_account()
    if account is None:
        return []
    orgs = sorted(account.organizations, key=lambda o: o.name or "")
    if has_account_wide_access(user, account):
        return orgs
    m = _membership(user, account.id)
    if m is None:
        return []
    allowed = {a.organization_id for a in m.assignments if a.organization_id is not None}
    return [o for o in orgs if o.id in allowed]


def current_account_id():
    acc = current_account()
    return acc.id if acc else None


def set_active_account(account_id):
    session["active_account_id"] = account_id
    session.pop("active_organization_id", None)


def set_active_organization(organization_id):
    if organization_id:
        session["active_organization_id"] = organization_id
    else:
        session.pop("active_organization_id", None)


def active_organization_id():
    if not has_request_context():
        return None
    return session.get("active_organization_id")


def initialize_active_context(user):
    """Nach dem Login: aktiven Account setzen und – falls das Mitglied KEINE
    accountweite Rolle hat – eine Standard-Organisation aus seinen pro-Org-
    Zuweisungen vorwaehlen, damit die Berechtigungen sofort greifen."""
    membership = Membership.query.filter_by(user_id=user.id).first()
    if membership is None:
        session.pop("active_account_id", None)
        session.pop("active_organization_id", None)
        return
    set_active_account(membership.account_id)  # setzt Account, leert Org
    has_account_wide = any(a.organization_id is None for a in membership.assignments)
    if not has_account_wide:
        per_org = next((a.organization_id for a in membership.assignments
                        if a.organization_id is not None), None)
        if per_org:
            set_active_organization(per_org)


# ── Mitgliedschaft / Permissions ───────────────────────────────────────────
def _membership(user, account_id):
    if not account_id:
        return None
    return Membership.query.filter_by(user_id=user.id, account_id=account_id).first()


def user_has_permission(user, permission_key, organization_id=None, account=None):
    """True, wenn der User in der gegebenen (oder aktiven) Organisation/Account das Recht hat.
    Accountweite Zuweisungen (organization_id IS NULL) gelten ueberall."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_super_admin", False):
        return True
    account = account or current_account()
    if account is None:
        return False
    membership = _membership(user, account.id)
    if membership is None:
        return False
    if organization_id is None:
        organization_id = active_organization_id()
    for asg in membership.assignments:
        applies = asg.organization_id is None or (
            organization_id is not None and asg.organization_id == organization_id
        )
        if applies and permission_key in asg.access_role.permission_keys:
            return True
    # Ohne konkreten Org-Kontext (account-weite Seite / keine aktive Org): das
    # Recht genuegt, wenn es in IRGENDEINER Organisation des Mitglieds vorhanden
    # ist. Verhindert 403-Lockouts, wenn keine aktive Organisation gesetzt ist.
    if organization_id is None:
        for asg in membership.assignments:
            if permission_key in asg.access_role.permission_keys:
                return True
    return False


def require_permission(permission_key):
    """Decorator: erfordert Login + Permission im aktiven Account/Org-Kontext."""
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if not user_has_permission(current_user, permission_key):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ── Login-Protokoll ──────────────────────────────────────────────────────
def client_ip():
    if not has_request_context():
        return None
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.headers.get("X-Real-IP") or request.remote_addr


def record_login(user, email, success):
    from app.models import LoginEvent
    ev = LoginEvent(
        user_id=user.id if user else None,
        email=(email or "").strip().lower() or None,
        success=success,
        host=request.host if has_request_context() else None,
        ip=client_ip(),
    )
    db.session.add(ev)
    db.session.commit()


# ── Passwoerter ────────────────────────────────────────────────────────────
def set_password(user, raw):
    user.password_hash = generate_password_hash(raw)


def verify_password(user, raw):
    return bool(user.password_hash) and check_password_hash(user.password_hash, raw)


# ── "mindestens ein Account-Admin" ─────────────────────────────────────────
def account_admin_membership_ids(account_id):
    """Memberships, die accountweit (organization_id IS NULL) ein Recht zur
    Mitgliederverwaltung haben = wirksame Account-Admins."""
    ids = set()
    memberships = Membership.query.filter_by(account_id=account_id).all()
    for m in memberships:
        for asg in m.assignments:
            if asg.organization_id is None and P_ACCOUNT_MEMBERS in asg.access_role.permission_keys:
                ids.add(m.id)
                break
    return ids


def is_last_account_admin(membership):
    admins = account_admin_membership_ids(membership.account_id)
    return membership.id in admins and len(admins) <= 1


# ── Einladungen ────────────────────────────────────────────────────────────
def create_invitation(account_id, email, access_role_id, organization_id=None):
    inv = Invitation(
        account_id=account_id,
        email=email.strip().lower(),
        access_role_id=access_role_id,
        organization_id=organization_id,
        token=secrets.token_urlsafe(32),
        status="pending",
    )
    db.session.add(inv)
    db.session.commit()
    return inv


def accept_invitation(token, name, raw_password):
    """Loest eine Einladung ein: User anlegen/finden, Membership + RoleAssignment."""
    from datetime import datetime
    inv = Invitation.query.filter_by(token=token, status="pending").first()
    if inv is None:
        return None, "Einladung ungueltig oder bereits eingeloest."
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        return None, "Einladung abgelaufen."

    user = User.query.filter_by(email=inv.email).first()
    if user is None:
        user = User(name=name.strip() or inv.email, email=inv.email)
        set_password(user, raw_password)
        db.session.add(user)
        db.session.flush()

    membership = Membership.query.filter_by(user_id=user.id, account_id=inv.account_id).first()
    if membership is None:
        membership = Membership(user_id=user.id, account_id=inv.account_id)
        db.session.add(membership)
        db.session.flush()

    exists = RoleAssignment.query.filter_by(
        membership_id=membership.id,
        access_role_id=inv.access_role_id,
        organization_id=inv.organization_id,
    ).first()
    if exists is None:
        db.session.add(RoleAssignment(
            membership_id=membership.id,
            access_role_id=inv.access_role_id,
            organization_id=inv.organization_id,
        ))

    inv.status = "accepted"
    db.session.commit()
    return user, None
