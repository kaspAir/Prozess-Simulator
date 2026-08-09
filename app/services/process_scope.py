"""Sichtbarkeit von Prozessen.

Prozesse werden immer auf den aktiven Account eingegrenzt und – wenn im Kopf
eine Organisation gewählt ist – zusätzlich auf diese Organisation. Bei «ganzer
Account» (keine aktive Organisation) bleiben alle Prozesse des Accounts sichtbar.
So bleiben die Prozesslandkarten verschiedener Organisationen sauber getrennt.
"""
from app.models import Process, Role, Function
from app.auth.service import current_account_id, active_organization_id


def _scoped(model, query=None):
    """Grenzt eine Query auf den aktiven Account und – falls eine Organisation im
    Kopf gewählt ist – auf diese Organisation ein. Bei «ganzer Account» (keine
    aktive Organisation) bleiben alle Datensätze des Accounts sichtbar."""
    q = query if query is not None else model.query
    acc = current_account_id()
    if acc is not None:
        q = q.filter(model.account_id == acc)
    org = active_organization_id()
    if org is not None:
        q = q.filter(model.organization_id == org)
    return q


def scoped_processes(query=None):
    return _scoped(Process, query)


def scoped_roles(query=None):
    return _scoped(Role, query)


def scoped_functions(query=None):
    return _scoped(Function, query)
