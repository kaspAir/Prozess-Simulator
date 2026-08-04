"""Modell-Export (JSON/XML) für einen Account: Organisationen, Einheiten, Rollen,
Funktionen, Personen und Prozesse (inkl. Nodes/Edges = Parameter).

Deterministisch und ohne KI: liest den aktuellen Datenbestand und serialisiert ihn.
"""
# Nur Serialisierung (kein Parsen von fremdem XML) -> XXE-Vektor greift hier nicht.
import xml.etree.ElementTree as ET  # nosec B405
from datetime import datetime, timezone

from app.models import Organization, OrgUnit, Role, Function, Person, Process
from app.services.node_to_bpmn import node_to_bpmn
from app.version import APP_VERSION


def _unit(u):
    return {
        "id": u.id,
        "name": u.name,
        "unit_type": u.unit_type,
        "parent_id": u.parent_id,
        "sort_order": u.sort_order,
        "person_id": u.person_id,
        "role_ids": [r.id for r in u.roles],
    }


def _node(n):
    return {
        "id": n.id,
        "name": n.name,
        "type": n.type,
        "effort_minutes": n.effort_minutes,
        "sort_order": n.sort_order,
        "x": n.x,
        "y": n.y,
        "legal_basis": n.legal_basis,
        "subprocess_id": n.subprocess_id,
        "role_ids": [r.id for r in n.roles],
        "required_function_ids": [f.id for f in n.required_functions],
        "assigned_position_ids": [p.id for p in n.assigned_positions],
    }


def _edges_of(process):
    edges = []
    for node in process.nodes:
        for e in (node.outgoing_edges or []):
            edges.append({
                "id": e.id,
                "source_node_id": e.source_node_id,
                "target_node_id": e.target_node_id,
                "condition": e.condition,
                "probability_percent": e.probability_percent,
            })
    return sorted(edges, key=lambda e: e["id"])


def build_model_export(account_id):
    """Baut die Export-Datenstruktur für den gegebenen Account."""
    orgs = (Organization.query.filter_by(account_id=account_id)
            .order_by(Organization.name).all())
    roles = Role.query.filter_by(account_id=account_id).order_by(Role.name).all()
    functions = Function.query.filter_by(account_id=account_id).order_by(Function.name).all()
    persons = Person.query.filter_by(account_id=account_id).order_by(Person.name).all()
    processes = Process.query.filter_by(account_id=account_id).order_by(Process.name).all()

    return {
        "meta": {
            "application": "Prozess-Simulator",
            "version": APP_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "account_id": account_id,
        },
        "organizations": [{
            "id": o.id,
            "name": o.name,
            "description": o.description,
            "units": [_unit(u) for u in OrgUnit.query.filter_by(organization_id=o.id)
                      .order_by(OrgUnit.sort_order, OrgUnit.name).all()],
        } for o in orgs],
        "roles": [{
            "id": r.id, "name": r.name, "parent_id": r.parent_id,
            "function_ids": [f.id for f in r.functions],
        } for r in roles],
        "functions": [{
            "id": f.id, "name": f.name, "description": f.description,
        } for f in functions],
        "persons": [{
            "id": p.id, "name": p.name, "organization_id": p.organization_id,
            "annual_salary": p.annual_salary, "fte": p.fte, "active": p.active,
            "role_ids": [r.id for r in p.roles],
            "function_ids": [f.id for f in p.functions],
        } for p in persons],
        "processes": [{
            "id": pr.id, "name": pr.name,
            "parent_process_id": pr.parent_process_id,
            "owner_org_unit_id": pr.owner_org_unit_id,
            # BPMN ist das führende Modell: vorhandenes XML, sonst aus Node/Edge erzeugt.
            "bpmn_xml": (pr.bpmn_xml or "").strip() or node_to_bpmn(pr),
            "nodes": [_node(n) for n in sorted(pr.nodes, key=lambda n: (n.sort_order, n.id))],
            "edges": _edges_of(pr),
        } for pr in processes],
    }


# ── XML-Serialisierung ──────────────────────────────────────────────────────
_SINGULAR = {
    "organizations": "organization", "units": "unit", "roles": "role",
    "functions": "function", "persons": "person", "processes": "process",
    "nodes": "node", "edges": "edge", "role_ids": "role_id",
    "function_ids": "function_id", "required_function_ids": "required_function_id",
    "assigned_position_ids": "assigned_position_id",
}


def _singular(tag):
    if tag in _SINGULAR:
        return _SINGULAR[tag]
    return tag[:-1] if tag.endswith("s") else tag + "_item"


def _to_xml(tag, value):
    el = ET.Element(tag)
    if isinstance(value, dict):
        for k, v in value.items():
            el.append(_to_xml(k, v))
    elif isinstance(value, (list, tuple)):
        for item in value:
            el.append(_to_xml(_singular(tag), item))
    else:
        el.text = "" if value is None else str(value)
    return el


def model_to_xml(data):
    """Serialisiert die Export-Struktur als XML-String (mit Deklaration)."""
    root = _to_xml("model", data)
    xml_bytes = ET.tostring(root, encoding="utf-8")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes
