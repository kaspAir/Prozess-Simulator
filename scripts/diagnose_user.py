"""Diagnose: Warum kommt ein Benutzer nach erfolgreichem Login auf ein 403?

Read-only. Zeigt fuer eine E-Mail alle Accounts/Memberships/Rollenzuweisungen
und deren Permissions und faellt ein klares Urteil, ob im *aktiven* Account das
Recht `dashboard.view` wirksam greift (genau das prueft der /dashboard-Guard).

Verbindet sich mit derselben DB wie die App (DATABASE_URL aus der .env). Auf dem
Test-Server also automatisch mit der Test-DB.

  python scripts/diagnose_user.py daniel@ditwi.ch
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app                                   # noqa: E402
from app.models import db, User, Account, Membership         # noqa: E402
from app.auth.permissions import P_DASHBOARD_VIEW            # noqa: E402


def _org_label(asg):
    if asg.organization_id is None:
        return "accountweit (alle Organisationen)"
    org = asg.organization
    return f"nur Organisation #{asg.organization_id} ({org.name if org else '??'})"


def diagnose(email):
    email = (email or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if user is None:
        print(f"[FEHLER] Kein Benutzer mit E-Mail {email!r} in dieser DB.")
        print("         -> Der Login kann so gar nicht erfolgreich sein. Falscher Account/DB?")
        return

    print(f"[OK] Benutzer gefunden: #{user.id}  {user.name!r}  <{user.email}>")
    print(f"     super_admin: {getattr(user, 'is_super_admin', False)}  "
          f"Passwort gesetzt: {bool(user.password_hash)}")
    if getattr(user, "is_super_admin", False):
        print("     -> super_admin umgeht alle Rechte; dieser Nutzer wuerde NIE 403 sehen.")

    memberships = Membership.query.filter_by(user_id=user.id).all()
    if not memberships:
        print("\n[FEHLER] KEINE Mitgliedschaft in irgendeinem Account.")
        print("         -> Login klappt, aber jede geschuetzte Seite gibt 403.")
        print("         Fix: Benutzer unter Verwaltung -> Mitglieder dem Account mit einer")
        print("              Rolle hinzufuegen (jede Vorlagen-Rolle enthaelt 'Dashboard ansehen').")
        return

    # So loest current_account() den aktiven Account auf, wenn die Session leer ist:
    active = memberships[0]
    print(f"\nMitgliedschaften ({len(memberships)}):")
    for m in memberships:
        acc = db.session.get(Account, m.account_id)
        marker = "   <-- wird nach Login als AKTIV gewaehlt (erste Mitgliedschaft)" \
            if m.id == active.id else ""
        print(f"\n  - Account #{m.account_id} ({acc.name if acc else '??'}){marker}")
        if not m.assignments:
            print("      [FEHLER] keine Rollenzuweisung -> in diesem Account KEIN Recht.")
            continue
        for asg in m.assignments:
            role = asg.access_role
            keys = sorted(role.permission_keys) if role else []
            has_dash = P_DASHBOARD_VIEW in keys
            flag = "hat dashboard.view" if has_dash else "OHNE dashboard.view (!)"
            print(f"      * Rolle {role.name!r} [{flag}] - {_org_label(asg)}")
            print(f"        Permissions: {', '.join(keys) or '(leer!)'}")

    # Urteil fuer den aktiven Account - repliziert user_has_permission(dashboard.view)
    print("\n" + "=" * 60)
    acc = db.session.get(Account, active.account_id)
    granting = [a for a in active.assignments
                if a.access_role and P_DASHBOARD_VIEW in a.access_role.permission_keys]
    if not active.assignments:
        verdict = "403 - aktive Mitgliedschaft hat gar keine Rolle."
    elif not granting:
        verdict = "403 - keine Rolle im aktiven Account enthaelt 'dashboard.view'."
    else:
        acctwide = [a for a in granting if a.organization_id is None]
        if acctwide:
            verdict = "OK - accountweite Rolle mit dashboard.view greift ueberall."
        else:
            orgs = ", ".join(f"#{a.organization_id}" for a in granting)
            verdict = ("OK - org-gebundene Rolle mit dashboard.view; nach Login wird "
                       f"eine dieser Organisationen ({orgs}) aktiv gesetzt.")
    print(f"Aktiver Account: #{active.account_id} ({acc.name if acc else '??'})")
    print(f"Urteil /dashboard: {verdict}")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Aufruf: python scripts/diagnose_user.py <email>")
        sys.exit(2)
    app = create_app()
    with app.app_context():
        diagnose(sys.argv[1])
