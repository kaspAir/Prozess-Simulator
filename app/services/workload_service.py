"""Prozessübergreifende Personen-Auslastung (Punkt 3, erster Baustein).

Summiert die erwartete Belastung jeder Person über ALLE (Einstiegs-)Prozesse eines
Accounts – bei einem gewählten Mengengerüst je Prozess – und stellt sie der
Jahreskapazität gegenüber. Damit wird sichtbar, wenn dieselbe Person in mehreren
unabhängigen Prozessen steckt und dadurch überlastet ist.

Der Aufwand einer Aktivität wird gleichmässig auf ihre zugeordneten Personen
verteilt (eine Aktivität wird je Fall einmal erledigt, geteilt durch die Zahl der
zuständigen Personen). Subprozesse sind über analyze_bpmn bereits eingerechnet.
Deterministisch, kein LLM.
"""
import re

from app.models import Process, Person
from app.services.bpmn_simulation import analyze_bpmn, ANNUAL_WORKING_MINUTES
from app.services.node_to_bpmn import effective_bpmn


def entry_processes(account_id):
    """Prozesse, die NICHT als Subprozess eines anderen aufgerufen werden – nur
    diese bekommen ein eigenes Mengengerüst (Subprozesse zählen über den Aufruf)."""
    procs = Process.query.filter_by(account_id=account_id).order_by(Process.name).all()
    called = set()
    for p in procs:
        for m in re.finditer(r'pros:subprocessId="(\d+)"', effective_bpmn(p) or ""):
            called.add(int(m.group(1)))
    return [p for p in procs if p.id not in called]


def cross_process_workload(account_id, volumes):
    """volumes: {process_id: Fälle/Jahr}. Gibt je Person Belastung/Kapazität/Auslastung
    (in Stunden/Jahr) zurück, plus die nicht zugeordnete Belastung."""
    load_min, unassigned_min = {}, 0.0
    for pr in Process.query.filter_by(account_id=account_id).all():
        vol = float(volumes.get(pr.id) or 0)
        if vol <= 0:
            continue
        res = analyze_bpmn(pr)
        if not res["has_model"]:
            continue
        for a in res["activities"]:
            mins = (a["expected_effort"] or 0) * vol
            if mins <= 0:
                continue
            persons = a.get("persons") or []
            if not persons:
                unassigned_min += mins
                continue
            share = mins / len(persons)
            for p in persons:
                load_min[p["id"]] = load_min.get(p["id"], 0.0) + share

    rows = []
    if load_min:
        pobj = {p.id: p for p in Person.query.filter(Person.id.in_(load_min.keys())).all()}
        for pid, mins in load_min.items():
            p = pobj.get(pid)
            fte = (p.fte if p and p.fte is not None else 1.0)
            cap = fte * ANNUAL_WORKING_MINUTES
            util = (mins / cap) if cap else 0.0
            status = "ok" if util <= 0.85 else ("eng" if util <= 1.0 else "Engpass")
            rows.append({
                "id": pid, "name": (p.name if p else "?"), "fte": fte,
                "load_h": mins / 60.0, "capacity_h": cap / 60.0,
                "util": util, "status": status,
            })
        rows.sort(key=lambda r: r["util"], reverse=True)
    return {"persons": rows, "unassigned_h": unassigned_min / 60.0}
