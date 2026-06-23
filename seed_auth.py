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

from app import create_app
from app.models import (
    db, Account, Organization, Process, Role, Function, Activity, Person,
    User, Membership, AccessRole, AccessRolePermission, RoleAssignment,
)
from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE
from app.auth.service import set_password

SCOPED_MODELS = (Organization, Process, Role, Function, Activity, Person)


def run():
    app = create_app()
    with app.app_context():
        db.create_all()

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
