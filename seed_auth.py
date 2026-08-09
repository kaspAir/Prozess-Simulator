"""Idempotenter Auth-Seed.

Legt einen Bootstrap-Account an, ordnet bestehende (account-lose) Daten diesem
Account zu, seedet die Vorlagen-Rollen und – falls ENV gesetzt – einen
Super-Admin als Account-Admin. Mehrfach ausfuehrbar (kein Doppel-Seed).

ENV:
  BOOTSTRAP_ACCOUNT_NAME   (default "ditwi")
  BOOTSTRAP_ADMIN_NAME     (default "Admin")
  BOOTSTRAP_ADMIN_EMAIL    (ohne -> kein Admin angelegt)
  BOOTSTRAP_ADMIN_PASSWORD
"""
import os

from sqlalchemy import inspect, text

from app import create_app
from app.models import (
    db, Account, Organization, OrgUnit, Process, Role, Function, Activity, Person,
    User, Membership, AccessRole, AccessRolePermission, RoleAssignment,
)
from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE
from app.auth.service import set_password

SCOPED_MODELS = (Organization, Process, Role, Function, Activity, Person)


def ensure_account_columns():
    """Ergaenzt fehlende account_id-Spalten in bereits existierenden Tabellen.
    db.create_all() legt nur fehlende TABELLEN an, aber keine neuen SPALTEN -
    daher diese leichtgewichtige, datenerhaltende Migration."""
    insp = inspect(db.engine)
    existing = set(insp.get_table_names())
    for Model in SCOPED_MODELS:
        table = Model.__tablename__
        if table not in existing:
            continue
        cols = [c["name"] for c in insp.get_columns(table)]
        if "account_id" not in cols:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN account_id INTEGER"))
            print(f"  + Spalte account_id zu {table} ergaenzt")
    db.session.commit()


def ensure_process_bpmn_column():
    """Ergaenzt die bpmn_xml-Spalte in processes (datenerhaltend)."""
    insp = inspect(db.engine)
    if "processes" not in set(insp.get_table_names()):
        return
    cols = [c["name"] for c in insp.get_columns("processes")]
    if "bpmn_xml" not in cols:
        db.session.execute(text("ALTER TABLE processes ADD COLUMN bpmn_xml TEXT"))
        print("  + Spalte bpmn_xml zu processes ergaenzt")
        db.session.commit()


def ensure_process_annual_cases_column():
    """Ergaenzt die annual_cases-Spalte in processes (datenerhaltend)."""
    insp = inspect(db.engine)
    if "processes" not in set(insp.get_table_names()):
        return
    cols = [c["name"] for c in insp.get_columns("processes")]
    if "annual_cases" not in cols:
        db.session.execute(text(
            "ALTER TABLE processes ADD COLUMN annual_cases FLOAT NOT NULL DEFAULT 0"))
        print("  + Spalte annual_cases zu processes ergaenzt")
        db.session.commit()


def ensure_process_priority_column():
    """Ergaenzt die priority-Spalte in processes (datenerhaltend)."""
    insp = inspect(db.engine)
    if "processes" not in set(insp.get_table_names()):
        return
    cols = [c["name"] for c in insp.get_columns("processes")]
    if "priority" not in cols:
        db.session.execute(text(
            "ALTER TABLE processes ADD COLUMN priority INTEGER NOT NULL DEFAULT 2"))
        print("  + Spalte priority zu processes ergaenzt")
        db.session.commit()


def ensure_process_type_column():
    """Ergaenzt die process_type-Spalte in processes (datenerhaltend)."""
    insp = inspect(db.engine)
    if "processes" not in set(insp.get_table_names()):
        return
    cols = [c["name"] for c in insp.get_columns("processes")]
    if "process_type" not in cols:
        db.session.execute(text("ALTER TABLE processes ADD COLUMN process_type VARCHAR(120)"))
        print("  + Spalte process_type zu processes ergaenzt")
        db.session.commit()


def ensure_process_organization_id_column():
    """Ergaenzt die organization_id-Spalte in processes (datenerhaltend). Bindet
    Prozesse an eine Organisation, damit die Prozesslandkarten getrennt bleiben."""
    insp = inspect(db.engine)
    if "processes" not in set(insp.get_table_names()):
        return
    cols = [c["name"] for c in insp.get_columns("processes")]
    if "organization_id" not in cols:
        db.session.execute(text("ALTER TABLE processes ADD COLUMN organization_id INTEGER"))
        print("  + Spalte organization_id zu processes ergaenzt")
        db.session.commit()


def ensure_role_function_organization_columns():
    """Ergaenzt organization_id in roles und functions (datenerhaltend)."""
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    for table in ("roles", "functions"):
        if table not in tables:
            continue
        cols = [c["name"] for c in insp.get_columns(table)]
        if "organization_id" not in cols:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN organization_id INTEGER"))
            print(f"  + Spalte organization_id zu {table} ergaenzt")
            db.session.commit()


def backfill_role_function_organization():
    """Ordnet bestehende Rollen/Funktionen ihrer Organisation zu (verlustfrei,
    geteilte werden je Mandant dupliziert)."""
    insp = inspect(db.engine)
    if "roles" not in set(insp.get_table_names()):
        return
    from app.services.tenant_backfill import backfill_all
    changed = backfill_all()
    if changed:
        print(f"  + {changed} Rolle(n)/Funktion(en) je Mandant getrennt (Backfill)")


def backfill_process_organization():
    """Ordnet bestehende Prozesse ohne Organisation einer zu: nach dem Process
    Owner (dessen Organisation), sonst – wenn der Account genau EINE Organisation
    hat – dieser. Mehrdeutige Fälle bleiben offen (in der Gesamtsicht sichtbar)."""
    insp = inspect(db.engine)
    if "processes" not in set(insp.get_table_names()):
        return
    changed = 0
    for pr in Process.query.filter(Process.organization_id.is_(None)).all():
        org_id = None
        if pr.owner_org_unit_id:
            unit = OrgUnit.query.get(pr.owner_org_unit_id)
            if unit:
                org_id = unit.organization_id
        if org_id is None and pr.account_id:
            orgs = Organization.query.filter_by(account_id=pr.account_id).all()
            if len(orgs) == 1:
                org_id = orgs[0].id
        if org_id:
            pr.organization_id = org_id
            changed += 1
    if changed:
        db.session.commit()
        print(f"  + {changed} Prozess(e) einer Organisation zugeordnet (Backfill)")


def run():
    app = create_app()
    with app.app_context():
        db.create_all()
        ensure_account_columns()
        ensure_process_bpmn_column()
        ensure_process_annual_cases_column()
        ensure_process_priority_column()
        ensure_process_type_column()
        ensure_process_organization_id_column()
        ensure_role_function_organization_columns()
        backfill_process_organization()
        backfill_role_function_organization()

        # 1) Bootstrap-Account
        account = Account.query.first()
        if account is None:
            account = Account(name=os.getenv("BOOTSTRAP_ACCOUNT_NAME", "ditwi"))
            db.session.add(account)
            db.session.commit()
            print(f"Account '{account.name}' angelegt.")

        # 2) Bestehende account-lose Daten zuordnen
        for Model in SCOPED_MODELS:
            Model.query.filter_by(account_id=None).update({"account_id": account.id})
        db.session.commit()

        # 3) Vorlagen-Rollen seeden
        for name, perms in TEMPLATE_ROLES.items():
            role = AccessRole.query.filter_by(account_id=account.id, name=name).first()
            if role is None:
                role = AccessRole(account_id=account.id, name=name, is_template=True)
                db.session.add(role)
                db.session.flush()
                for p in perms:
                    db.session.add(AccessRolePermission(access_role_id=role.id, permission_key=p))
        db.session.commit()

        # 4) Super-Admin / Account-Admin
        email = (os.getenv("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
        if not email or not password:
            print("BOOTSTRAP_ADMIN_EMAIL/PASSWORD nicht gesetzt – kein Admin angelegt.")
            print("Auth-Seed abgeschlossen.")
            return

        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(name=os.getenv("BOOTSTRAP_ADMIN_NAME", "Admin"),
                        email=email, is_super_admin=True)
            set_password(user, password)
            db.session.add(user)
            db.session.flush()
            print(f"Super-Admin '{email}' angelegt.")
        else:
            user.is_super_admin = True

        membership = Membership.query.filter_by(user_id=user.id, account_id=account.id).first()
        if membership is None:
            membership = Membership(user_id=user.id, account_id=account.id)
            db.session.add(membership)
            db.session.flush()

        admin_role = AccessRole.query.filter_by(account_id=account.id, name=ACCOUNT_ADMIN_ROLE).first()
        if admin_role and RoleAssignment.query.filter_by(
            membership_id=membership.id, access_role_id=admin_role.id, organization_id=None
        ).first() is None:
            db.session.add(RoleAssignment(
                membership_id=membership.id, access_role_id=admin_role.id, organization_id=None))

        db.session.commit()
        print(f"Super-Admin/Account-Admin bereit: {email}")
        print("Auth-Seed abgeschlossen.")


if __name__ == "__main__":
    run()
