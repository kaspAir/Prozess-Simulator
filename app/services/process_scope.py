"""Sichtbarkeit von Prozessen.

Prozesse werden immer auf den aktiven Account eingegrenzt und – wenn im Kopf
eine Organisation gewählt ist – zusätzlich auf diese Organisation. Bei «ganzer
Account» (keine aktive Organisation) bleiben alle Prozesse des Accounts sichtbar.
So bleiben die Prozesslandkarten verschiedener Organisationen sauber getrennt.
"""
from app.models import Process
from app.auth.service import current_account_id, active_organization_id


def scoped_processes(query=None):
    """Grenzt eine Process-Query auf Account + aktive Organisation ein."""
    q = query if query is not None else Process.query
    acc = current_account_id()
    if acc is not None:
        q = q.filter(Process.account_id == acc)
    org = active_organization_id()
    if org is not None:
        q = q.filter(Process.organization_id == org)
    return q
