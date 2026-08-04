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

from app.models import Process, Person, Function, Role, OrgUnit, Organization
from app.services.bpmn_simulation import analyze_bpmn, ANNUAL_WORKING_MINUTES
from app.services.node_to_bpmn import effective_bpmn

PRIORITY_LABELS = {1: "Hoch", 2: "Mittel", 3: "Niedrig"}
WORKING_DAYS_PER_YEAR = 220        # Annahme für die Umrechnung Jahr <-> Tag


def _status(util):
    return "ok" if util <= 0.85 else ("eng" if util <= 1.0 else "Engpass")


def _covered_functions(person):
    """Funktions-IDs, die eine Person abdeckt – direkt oder über eine ihrer Rollen."""
    s = {f.id for f in person.functions}
    for r in person.roles:
        s.update(f.id for f in r.functions)
    return s


def entry_processes(account_id):
    """Prozesse, die NICHT als Subprozess eines anderen aufgerufen werden – nur
    diese bekommen ein eigenes Mengengerüst (Subprozesse zählen über den Aufruf)."""
    procs = Process.query.filter_by(account_id=account_id).order_by(Process.name).all()
    called = set()
    for p in procs:
        for m in re.finditer(r'pros:subprocessId="(\d+)"', effective_bpmn(p) or ""):
            called.add(int(m.group(1)))
    return [p for p in procs if p.id not in called]


def cross_process_workload(account_id, volumes, capacity_per_fte=ANNUAL_WORKING_MINUTES):
    """volumes: {process_id: Fallzahl}. Gibt je Person Belastung/Kapazität/Auslastung
    zurück (Stunden), plus die nicht zugeordnete Belastung. capacity_per_fte ist die
    Kapazität einer 100%-Stelle im betrachteten Zeitraum (Standard: Jahr) – für die
    Lastperiode wird stattdessen die Fenster-Kapazität übergeben."""
    load_min, unassigned_min = {}, 0.0
    needed_fn, needed_role = {}, {}   # person_id -> benötigte Funktions-/Rollen-IDs
    per_process = {}                  # person_id -> {process_id -> Minuten}
    proc_meta = {}                    # process_id -> {name, priority}
    for pr in Process.query.filter_by(account_id=account_id).all():
        vol = float(volumes.get(pr.id) or 0)
        if vol <= 0:
            continue
        res = analyze_bpmn(pr)
        if not res["has_model"]:
            continue
        proc_meta[pr.id] = {"name": pr.name, "priority": (pr.priority or 2)}
        for a in res["activities"]:
            mins = (a["expected_effort"] or 0) * vol
            persons = a.get("persons") or []
            if not persons:
                if mins > 0:
                    unassigned_min += mins
                continue
            share = mins / len(persons)
            for p in persons:
                load_min[p["id"]] = load_min.get(p["id"], 0.0) + share
                per_process.setdefault(p["id"], {})
                per_process[p["id"]][pr.id] = per_process[p["id"]].get(pr.id, 0.0) + share
                needed_fn.setdefault(p["id"], set()).update(a.get("req_function_ids") or [])
                needed_role.setdefault(p["id"], set()).update(a.get("req_role_ids") or [])

    all_persons = Person.query.filter_by(account_id=account_id).all()
    covered = {p.id: _covered_functions(p) for p in all_persons}
    covered_roles = {p.id: {r.id for r in p.roles} for p in all_persons}
    # Nur Personen, die tatsächlich eine Stelle besetzen, kommen als Aushilfe infrage
    # (Personen ohne Stelle im Organigramm werden nicht als «frei» vorgeschlagen).
    placed = {u.person_id for u in (OrgUnit.query.join(Organization)
              .filter(Organization.account_id == account_id, OrgUnit.person_id.isnot(None)).all())}

    def capacity_min(p):
        return (p.fte if p.fte is not None else 1.0) * capacity_per_fte

    rows = []
    for p in all_persons:
        mins = load_min.get(p.id, 0.0)
        if mins <= 0:
            continue
        cap = capacity_min(p)
        util = (mins / cap) if cap else 0.0
        # Aufschlüsselung der Last nach Prozess/Priorität – hoch zuerst (schützen),
        # niedrig zuletzt (eher verschiebbar).
        by_process = []
        for proc_id, pm in per_process.get(p.id, {}).items():
            meta = proc_meta.get(proc_id, {"name": "?", "priority": 2})
            by_process.append({
                "process": meta["name"], "priority": meta["priority"],
                "priority_label": PRIORITY_LABELS.get(meta["priority"], "Mittel"),
                "load_h": pm / 60.0,
            })
        by_process.sort(key=lambda x: (x["priority"], -x["load_h"]))
        rows.append({
            "id": p.id, "name": p.name, "fte": (p.fte if p.fte is not None else 1.0),
            "load_h": mins / 60.0, "capacity_h": cap / 60.0, "util": util,
            "status": "ok" if util <= 0.85 else ("eng" if util <= 1.0 else "Engpass"),
            "by_process": by_process,
        })
    rows.sort(key=lambda r: r["util"], reverse=True)

    # ── Ausleih-Vorschläge: je überlasteter Person Kandidat:innen, die eine
    #    benötigte Funktion ODER Rolle abdecken UND freie Kapazität haben
    #    (Vorschlag, keine Entscheidung) ──
    fname = {f.id: f.name for f in Function.query.filter_by(account_id=account_id).all()}
    rname = {r.id: r.name for r in Role.query.filter_by(account_id=account_id).all()}
    borrow = []
    for r in rows:
        if r["util"] <= 1.0:
            continue
        need_f = needed_fn.get(r["id"]) or set()
        need_r = needed_role.get(r["id"]) or set()
        if not need_f and not need_r:
            continue
        cands = []
        for p in all_persons:
            if p.id == r["id"] or p.id not in placed:
                continue
            spare = capacity_min(p) - load_min.get(p.id, 0.0)
            if spare <= 0:
                continue
            ov_f = covered.get(p.id, set()) & need_f
            ov_r = covered_roles.get(p.id, set()) & need_r
            if not ov_f and not ov_r:
                continue
            covers = sorted(rname.get(i, "#%d" % i) for i in ov_r) + \
                sorted(fname.get(i, "#%d" % i) for i in ov_f)
            cands.append({
                "name": p.name, "spare_h": spare / 60.0,
                "match": len(ov_f) + len(ov_r), "covers": covers,
            })
        cands.sort(key=lambda c: (c["match"], c["spare_h"]), reverse=True)
        if cands:
            borrow.append({"name": r["name"], "util": r["util"], "candidates": cands[:5]})

    return {"persons": rows, "unassigned_h": unassigned_min / 60.0, "borrow": borrow}


def peak_workload(account_id, peak_process_id, factor, days):
    """Lastperiode («Peak»): Fenster von `days` Arbeitstagen; im gewählten Prozess
    wird die Fallzahl mit `factor` multipliziert, die übrigen laufen normal weiter.
    Auslastung je Person IN DER PERIODE (gegen die Fenster-Kapazität) – so wird ein
    temporärer Peak sichtbar, den der Jahresschnitt verschluckt."""
    days = max(1, days)
    window_volumes = {}
    for pr in Process.query.filter_by(account_id=account_id).all():
        annual = pr.annual_cases or 0
        if annual <= 0:
            continue
        per_day = annual / WORKING_DAYS_PER_YEAR
        f = factor if pr.id == peak_process_id else 1.0
        window_volumes[pr.id] = per_day * days * f
    window_cap = (ANNUAL_WORKING_MINUTES / WORKING_DAYS_PER_YEAR) * days
    return cross_process_workload(account_id, window_volumes, capacity_per_fte=window_cap)


def process_activity_ampel(account_id, volumes):
    """Ampel-Sicht fürs Dashboard: je Einstiegsprozess seine Aktivitäten mit
    rot/gelb/grün. Die Farbe einer Aktivität spiegelt die tatsächliche Überlast der
    Personen, die sie ausführen (prozessübergreifend gerechnet)."""
    wl = cross_process_workload(account_id, volumes)
    putil = {r["id"]: r["util"] for r in wl["persons"]}
    out = []
    for pr in entry_processes(account_id):
        vol = float(volumes.get(pr.id) or 0)
        if vol <= 0:
            continue
        res = analyze_bpmn(pr)
        if not res["has_model"]:
            continue
        acts = []
        for a in res["activities"]:
            persons = a.get("persons") or []
            if not persons:
                continue
            util = max(putil.get(p["id"], 0.0) for p in persons)
            acts.append({
                "name": a["name"], "effort": a["effort"],
                "persons": [p["name"] for p in persons],
                "util": util, "status": _status(util),
            })
        acts.sort(key=lambda x: x["util"], reverse=True)
        engpass = acts[0]["name"] if (acts and acts[0]["status"] == "Engpass") else None
        out.append({
            "process": pr.name, "priority": (pr.priority or 2),
            "priority_label": PRIORITY_LABELS.get(pr.priority or 2, "Mittel"),
            "activities": acts, "engpass": engpass,
            "has_unassigned": any((a.get("persons") in (None, [])) for a in res["activities"]),
        })
    return out
