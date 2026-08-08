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


def _process_query(account_id, organization_id):
    q = Process.query.filter_by(account_id=account_id)
    if organization_id is not None:
        q = q.filter_by(organization_id=organization_id)
    return q


def entry_processes(account_id, organization_id=None):
    """Prozesse, die NICHT als Subprozess eines anderen aufgerufen werden – nur
    diese bekommen ein eigenes Mengengerüst (Subprozesse zählen über den Aufruf).
    Auf die aktive Organisation eingegrenzt, wenn eine gewählt ist."""
    procs = _process_query(account_id, organization_id).order_by(Process.name).all()
    called = set()
    for p in procs:
        for m in re.finditer(r'pros:subprocessId="(\d+)"', effective_bpmn(p) or ""):
            called.add(int(m.group(1)))
    return [p for p in procs if p.id not in called]


def cross_process_workload(account_id, volumes, capacity_per_fte=ANNUAL_WORKING_MINUTES,
                           organization_id=None):
    """volumes: {process_id: Fallzahl}. Gibt je Person Belastung/Kapazität/Auslastung
    zurück (Stunden), plus die nicht zugeordnete Belastung. capacity_per_fte ist die
    Kapazität einer 100%-Stelle im betrachteten Zeitraum (Standard: Jahr) – für die
    Lastperiode wird stattdessen die Fenster-Kapazität übergeben. Prozesse UND
    Personen werden auf die aktive Organisation eingegrenzt, wenn eine gewählt ist –
    damit werden die Kapazitätsbilder verschiedener Organisationen nicht vermischt."""
    load_min, unassigned_min = {}, 0.0
    needed_fn, needed_role = {}, {}   # person_id -> benötigte Funktions-/Rollen-IDs
    per_process = {}                  # person_id -> {process_id -> Minuten}
    proc_meta = {}                    # process_id -> {name, priority}
    for pr in _process_query(account_id, organization_id).all():
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

    pq = Person.query.filter_by(account_id=account_id)
    if organization_id is not None:
        pq = pq.filter_by(organization_id=organization_id)
    all_persons = pq.all()
    covered = {p.id: _covered_functions(p) for p in all_persons}
    covered_roles = {p.id: {r.id for r in p.roles} for p in all_persons}
    # Nur Personen, die tatsächlich eine Stelle besetzen, kommen als Aushilfe infrage
    # (Personen ohne Stelle im Organigramm werden nicht als «frei» vorgeschlagen).
    uq = (OrgUnit.query.join(Organization)
          .filter(Organization.account_id == account_id, OrgUnit.person_id.isnot(None)))
    if organization_id is not None:
        uq = uq.filter(Organization.id == organization_id)
    placed = {u.person_id for u in uq.all()}

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
        # Priorität, die wir schützen: die höchste (= kleinste Zahl) unter den
        # Prozessen, in denen die überlastete Person steckt.
        target_prio = min((proc_meta[pid]["priority"]
                           for pid in per_process.get(r["id"], {})), default=2)
        cands = []
        for p in all_persons:
            if p.id == r["id"] or p.id not in placed:
                continue
            ov_f = covered.get(p.id, set()) & need_f
            ov_r = covered_roles.get(p.id, set()) & need_r
            if not ov_f and not ov_r:
                continue
            idle = max(0.0, capacity_min(p) - load_min.get(p.id, 0.0))
            # Kapazität, die durch Zurückstellen NIEDRIGER priorer Arbeit frei würde
            shift_min, shift_from = 0.0, []
            for pid, mins in per_process.get(p.id, {}).items():
                if proc_meta[pid]["priority"] > target_prio:   # niedriger prior
                    shift_min += mins
                    shift_from.append({"process": proc_meta[pid]["name"],
                                       "priority_label": PRIORITY_LABELS.get(
                                           proc_meta[pid]["priority"], "Mittel")})
            help_min = idle + shift_min
            if help_min <= 0:
                continue
            covers = sorted(rname.get(i, "#%d" % i) for i in ov_r) + \
                sorted(fname.get(i, "#%d" % i) for i in ov_f)
            cands.append({
                "name": p.name, "spare_h": idle / 60.0, "shift_h": shift_min / 60.0,
                "shift_from": shift_from, "help_h": help_min / 60.0,
                "match": len(ov_f) + len(ov_r), "covers": covers,
            })
        cands.sort(key=lambda c: (c["match"], c["help_h"]), reverse=True)
        if cands:
            borrow.append({"name": r["name"], "util": r["util"],
                           "target_prio_label": PRIORITY_LABELS.get(target_prio, "Mittel"),
                           "candidates": cands[:5]})

    # Systemische Machbarkeit: reicht die GESAMTE Kapazität der besetzten Stellen für
    # die Gesamtnachfrage? Wenn nein, ist die Überlast durch Umverteilen/Ausleihen
    # allein NICHT behebbar (dann braucht es Überstunden, mehr Personal oder eine
    # längere Frist).
    total_demand = sum(load_min.values()) + unassigned_min
    total_capacity = sum(capacity_min(p) for p in all_persons if p.id in placed)
    deficit = max(0.0, total_demand - total_capacity)

    return {"persons": rows, "unassigned_h": unassigned_min / 60.0, "borrow": borrow,
            "total_demand_h": total_demand / 60.0, "total_capacity_h": total_capacity / 60.0,
            "deficit_h": deficit / 60.0, "feasible": total_demand <= total_capacity}


def peak_workload(account_id, peak_process_id, peak_cases, days, organization_id=None):
    """Lastperiode («Peak»): Fenster von `days` Arbeitstagen; im gewählten Prozess
    werden `peak_cases` Durchläufe in der Periode angenommen (absolute Zahl), die
    übrigen Prozesse laufen mit ihrem normalen Tagespensum weiter. Auslastung je
    Person IN DER PERIODE (gegen die Fenster-Kapazität) – so wird ein temporärer
    Peak sichtbar, den der Jahresschnitt verschluckt."""
    days = max(1, days)
    window_volumes = {}
    for pr in _process_query(account_id, organization_id).all():
        annual = pr.annual_cases or 0
        if pr.id == peak_process_id:
            window_volumes[pr.id] = max(0.0, peak_cases)
        elif annual > 0:
            window_volumes[pr.id] = (annual / WORKING_DAYS_PER_YEAR) * days
    window_cap = (ANNUAL_WORKING_MINUTES / WORKING_DAYS_PER_YEAR) * days
    return cross_process_workload(account_id, window_volumes, capacity_per_fte=window_cap,
                                  organization_id=organization_id)


def process_activity_ampel(account_id, volumes, organization_id=None):
    """Ampel-Sicht fürs Dashboard: je Einstiegsprozess seine Aktivitäten mit
    rot/gelb/grün. Die Farbe einer Aktivität spiegelt die tatsächliche Überlast der
    Personen, die sie ausführen (prozessübergreifend gerechnet)."""
    wl = cross_process_workload(account_id, volumes, organization_id=organization_id)
    putil = {r["id"]: r["util"] for r in wl["persons"]}
    out = []
    for pr in entry_processes(account_id, organization_id):
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
