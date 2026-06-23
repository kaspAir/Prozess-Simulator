"""Berechtigungs-Katalog und Vorlagen-Rollen (Multi-Tenant RBAC).

Permission-Keys sind die Bausteine, aus denen (frei definierbare) AccessRoles
zusammengesetzt werden. Die Vorlagen-Rollen werden pro Account geseedet.
"""

# ── Permission-Keys ────────────────────────────────────────────────────────
P_ACCOUNT_MANAGE = "account.manage"
P_ACCOUNT_MEMBERS = "account.members.manage"
P_ACCOUNT_ROLES = "account.roles.manage"
P_ORG_CREATE = "org.create"
P_ORG_MANAGE = "org.manage"
P_ORGCHART_MANAGE = "orgchart.manage"
P_PERSONS_MANAGE = "persons.manage"
P_PROCESSES_MANAGE = "processes.manage"
P_SIMULATION_RUN = "simulation.run"
P_DASHBOARD_VIEW = "dashboard.view"

# Alle bekannten Permissions mit menschenlesbarem Label (fuer UI / Rollen-Editor).
ALL_PERMISSIONS = {
    P_ACCOUNT_MANAGE: "Account-Einstellungen verwalten",
    P_ACCOUNT_MEMBERS: "Mitglieder verwalten",
    P_ACCOUNT_ROLES: "Rollen verwalten",
    P_ORG_CREATE: "Organisationen anlegen",
    P_ORG_MANAGE: "Organisationen verwalten",
    P_ORGCHART_MANAGE: "Organigramm verwalten",
    P_PERSONS_MANAGE: "Mitarbeitende verwalten",
    P_PROCESSES_MANAGE: "Prozesse zeichnen/bearbeiten",
    P_SIMULATION_RUN: "Simulation ausfuehren",
    P_DASHBOARD_VIEW: "Dashboard ansehen",
}

# ── Vorlagen-Rollen: name -> set(permission_keys) ──────────────────────────
TEMPLATE_ROLES = {
    "Account-Admin": {
        P_ACCOUNT_MANAGE, P_ACCOUNT_MEMBERS, P_ACCOUNT_ROLES,
        P_ORG_CREATE, P_ORG_MANAGE,
        P_ORGCHART_MANAGE, P_PERSONS_MANAGE, P_PROCESSES_MANAGE,
        P_SIMULATION_RUN, P_DASHBOARD_VIEW,
    },
    "Organisations-Admin": {
        P_ORG_MANAGE, P_ORGCHART_MANAGE, P_PERSONS_MANAGE,
        P_PROCESSES_MANAGE, P_SIMULATION_RUN, P_DASHBOARD_VIEW,
    },
    "Organigramm-Editor": {P_ORGCHART_MANAGE, P_DASHBOARD_VIEW},
    "Mitarbeitende-Editor": {P_PERSONS_MANAGE, P_DASHBOARD_VIEW},
    "Prozess-Editor": {P_PROCESSES_MANAGE, P_SIMULATION_RUN, P_DASHBOARD_VIEW},
    "Viewer": {P_DASHBOARD_VIEW},
}

# Rolle, die als accountweiter Admin gilt (fuer "mindestens 1 Admin"-Regel).
ACCOUNT_ADMIN_ROLE = "Account-Admin"
