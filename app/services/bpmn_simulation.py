"""Berechnung aus dem BPMN-Modell: Aufwand & Kosten je Aktivität und Prozess-Summe.

Zwei Sichten:
- roh: jede Aktivität zählt genau einmal (Summe der erfassten Aufwände/Kosten).
- erwartet: mit den XOR-Pfad-Wahrscheinlichkeiten gewichtet (eine Aktivität hinter
  einem 40%-Pfad zählt 0,4x).

Kosten je Aktivität = Aufwand (Min.) x Minutenkosten der zugeordneten Stelle(n).
Die Minutenkosten stammen aus dem Jahresgehalt der besetzten Person (Organisation).

Deterministisch; das (nutzererstellte) BPMN-XML wird XXE-sicher mit defusedxml geparst.
"""
import defusedxml.ElementTree as DET

from app.models import OrgUnit, Organization

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
PROS_NS = "http://ditwi.ch/bpmn/pros"
ANNUAL_WORKING_MINUTES = 2100 * 60   # 2100 h/Jahr je 100%-Stelle

TASK_LOCALS = {"task", "userTask", "serviceTask", "sendTask", "receiveTask",
               "manualTask", "businessRuleTask", "scriptTask", "callActivity", "subProcess"}


def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _pros(el, name):
    return el.get("{%s}%s" % (PROS_NS, name))


def _minute_cost(person):
    return (person.annual_salary or 0) / ANNUAL_WORKING_MINUTES if person else 0.0


def _visit_factors(node_ids, starts, flows):
    """Erwartete Besuchshäufigkeit je Node (Start=1.0, XOR-Prob als Multiplikator)."""
    factors = {n: 0.0 for n in node_ids}
    for s in starts:
        factors[s] = 1.0
    if not starts:
        return {n: 1.0 for n in node_ids}   # ohne Start nicht propagierbar -> je 1x
    for _ in range(max(1, len(node_ids) * 2)):
        changed = False
        for f in flows:
            src = factors.get(f["source"], 0.0)
            if src <= 0:
                continue
            mult = (f["prob"] / 100.0) if f["prob"] is not None else 1.0
            cand = src * mult
            if cand > factors.get(f["target"], 0.0):
                factors[f["target"]] = cand
                changed = True
        if not changed:
            break
    return factors


def _empty():
    return {"has_model": False, "activities": [],
            "total_effort": 0.0, "expected_effort": 0.0,
            "total_cost": 0.0, "expected_cost": 0.0}


def analyze_bpmn(process):
    xml = (getattr(process, "bpmn_xml", None) or "").strip()
    if not xml:
        return _empty()
    try:
        root = DET.fromstring(xml)
    except Exception:
        return _empty()

    tasks, starts, flows, node_ids = {}, [], [], set()
    for el in root.iter():
        ln = _local(el.tag)
        eid = el.get("id")
        if ln == "sequenceFlow":
            prob = _pros(el, "probability")
            flows.append({
                "source": el.get("sourceRef"), "target": el.get("targetRef"),
                "prob": float(prob) if prob not in (None, "") else None,
            })
            node_ids.update([el.get("sourceRef"), el.get("targetRef")])
        elif not eid:
            continue
        elif ln == "startEvent":
            starts.append(eid)
            node_ids.add(eid)
        elif ln in TASK_LOCALS:
            tasks[eid] = el
            node_ids.add(eid)

    factors = _visit_factors(node_ids, starts, flows)

    # Stellen -> Personen (kontoscoped), für die Kostensätze
    acc_id = getattr(process, "account_id", None)
    pos_ids = set()
    for el in tasks.values():
        for x in (_pros(el, "positionIds") or "").split(","):
            if x.strip().isdigit():
                pos_ids.add(int(x))
    positions = {}
    if pos_ids:
        q = OrgUnit.query.join(Organization).filter(OrgUnit.id.in_(pos_ids))
        if acc_id is not None:
            q = q.filter(Organization.account_id == acc_id)
        positions = {p.id: p for p in q.all()}

    activities = []
    tot_e = exp_e = tot_c = exp_c = 0.0
    for eid, el in tasks.items():
        name = el.get("name") or eid
        effort = float(_pros(el, "effortMinutes") or 0)
        visit = factors.get(eid, 1.0)
        pids = [int(x) for x in (_pros(el, "positionIds") or "").split(",") if x.strip().isdigit()]
        pos = [positions[i] for i in pids if i in positions]
        persons = [p.person for p in pos if p.person]
        rate = (sum(_minute_cost(pp) for pp in persons) / len(persons)) if persons else 0.0

        raw_cost = effort * rate
        exp_effort = effort * visit
        exp_cost = exp_effort * rate

        activities.append({
            "id": eid, "name": name, "effort": effort, "visit_factor": visit,
            "raw_cost": raw_cost, "expected_effort": exp_effort, "expected_cost": exp_cost,
            "rate_per_min": rate,
            "legal_basis": _pros(el, "legalBasis") or "",
            "positions": [p.name for p in pos],
        })
        tot_e += effort
        exp_e += exp_effort
        tot_c += raw_cost
        exp_c += exp_cost

    activities.sort(key=lambda a: (a["name"] or "").lower())
    return {"has_model": True, "activities": activities,
            "total_effort": tot_e, "expected_effort": exp_e,
            "total_cost": tot_c, "expected_cost": exp_c}
