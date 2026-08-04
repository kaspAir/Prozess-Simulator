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

from app.models import OrgUnit, Organization, Person, Process, Role, Function

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
    """Erwartete Besuchshäufigkeit je Node.

    Start = 1.0. Für jeden Node ist der Wert die SUMME der einlaufenden Beiträge
    (Quelle x Pfad-Wahrscheinlichkeit). Damit zählen zusammenlaufende XOR-Zweige
    zusammen: ein Node hinter «60% ja» UND «40% nein (nach Umweg)» wird von 100%
    der Fälle besucht – nicht bloss vom stärkeren Zweig. Iterative Auswertung
    (Jacobi): exakt für azyklische Graphen, konvergent für Rücksprünge mit p<1.
    """
    node_ids = set(node_ids)
    start_set = set(starts)
    if not start_set:
        return {n: 1.0 for n in node_ids}   # ohne Start nicht propagierbar -> je 1x

    # Ausgehende Flows je Quelle -> bedingte Wahrscheinlichkeit P(Flow | Quelle).
    # Ein einzelner Ausgang = 100%. Bei mehreren Ausgängen (Verzweigung) gelten die
    # gesetzten Prozente; nicht gesetzte Zweige teilen sich den Rest zu gleichen
    # Teilen (XOR-Semantik – die Ausgänge summieren sich auf höchstens 100%).
    outgoing = {}
    for f in flows:
        outgoing.setdefault(f["source"], []).append(f)
    incoming = {}
    for src, outs in outgoing.items():
        if len(outs) == 1:
            conds = [1.0]
        else:
            set_total = sum(o["prob"] / 100.0 for o in outs if o["prob"] is not None)
            unset = [o for o in outs if o["prob"] is None]
            share = (max(0.0, 1.0 - set_total) / len(unset)) if unset else 0.0
            conds = [(o["prob"] / 100.0) if o["prob"] is not None else share for o in outs]
        for o, c in zip(outs, conds):
            incoming.setdefault(o["target"], []).append((src, c))

    factors = {n: (1.0 if n in start_set else 0.0) for n in node_ids}
    for _ in range(len(node_ids) + 2):
        changed = False
        new = {}
        for n in node_ids:
            val = 1.0 if n in start_set else sum(
                factors.get(src, 0.0) * p for src, p in incoming.get(n, []))
            new[n] = val
            if abs(val - factors.get(n, 0.0)) > 1e-9:
                changed = True
        factors = new
        if not changed:
            break
    return factors


def _empty():
    return {"has_model": False, "activities": [],
            "total_effort": 0.0, "expected_effort": 0.0,
            "total_cost": 0.0, "expected_cost": 0.0}


def analyze_bpmn(process, _seen=None):
    """Aufwand/Kosten eines Prozesses. CallActivities mit pros:subprocessId werden
    rekursiv eingerechnet (der Subprozess zählt zum Aufwand/den Kosten des Eltern-
    prozesses; im erwarteten Wert mit der Besuchshäufigkeit der CallActivity
    gewichtet). _seen verhindert Endlosschleifen bei zyklischen Verweisen."""
    seen = set(_seen or ())
    from app.services.node_to_bpmn import effective_bpmn
    # Gespeichertes BPMN, sonst aus dem Node-Modell erzeugt – damit die Kosten-
    # Analyse bestehende Prozesse ohne Export/Import mitrechnet (wie der Editor).
    xml = effective_bpmn(process).strip()
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

    # Ausdrücklich gewählte Mitarbeitende (verfeinern die Stellen für die Kosten)
    person_ids = set()
    for el in tasks.values():
        for x in (_pros(el, "personIds") or "").split(","):
            if x.strip().isdigit():
                person_ids.add(int(x))
    persons_by_id = {}
    if person_ids:
        pq = Person.query.filter(Person.id.in_(person_ids))
        if acc_id is not None:
            pq = pq.filter(Person.account_id == acc_id)
        persons_by_id = {p.id: p for p in pq.all()}

    # Verteilungsregel «alle mit der Rolle»: Personen je Rolle, die tatsächlich eine
    # Stelle besetzen. Fordert eine Aktivität eine Rolle (ohne konkrete Person), wird
    # die Arbeit gleichmässig auf ALLE diese Personen verteilt.
    persons_by_role = {}
    if acc_id is not None:
        placed_ids = {u.person_id for u in (OrgUnit.query.join(Organization)
                      .filter(Organization.account_id == acc_id,
                              OrgUnit.person_id.isnot(None)).all())}
        for p in Person.query.filter_by(account_id=acc_id).all():
            if p.id in placed_ids:
                for r in p.roles:
                    persons_by_role.setdefault(r.id, []).append(p)

    # Bedarf je Aktivität: benötigte Funktionen/Rollen -> Namen für die Lücken-Meldung
    req_fn_ids, req_role_ids = set(), set()
    for el in tasks.values():
        for x in (_pros(el, "functionIds") or "").split(","):
            if x.strip().isdigit():
                req_fn_ids.add(int(x))
        for x in (_pros(el, "roleIds") or "").split(","):
            if x.strip().isdigit():
                req_role_ids.add(int(x))
    fn_name, role_name = {}, {}
    if req_fn_ids:
        fq = Function.query.filter(Function.id.in_(req_fn_ids))
        if acc_id is not None:
            fq = fq.filter(Function.account_id == acc_id)
        fn_name = {f.id: f.name for f in fq.all()}
    if req_role_ids:
        rq = Role.query.filter(Role.id.in_(req_role_ids))
        if acc_id is not None:
            rq = rq.filter(Role.account_id == acc_id)
        role_name = {r.id: r.name for r in rq.all()}

    activities = []
    tot_e = exp_e = tot_c = exp_c = 0.0
    for eid, el in tasks.items():
        name = el.get("name") or eid
        effort = float(_pros(el, "effortMinutes") or 0)
        visit = factors.get(eid, 1.0)
        pids = [int(x) for x in (_pros(el, "positionIds") or "").split(",") if x.strip().isdigit()]
        pos = [positions[i] for i in pids if i in positions]
        # Personen: 1) ausdrücklich gewählte Mitarbeitende; sonst 2) ALLE mit einer
        # geforderten Rolle (gleichmässig verteilt); sonst 3) die Inhaber:innen der
        # gewählten Stellen.
        prsids = [int(x) for x in (_pros(el, "personIds") or "").split(",") if x.strip().isdigit()]
        persons = [persons_by_id[i] for i in prsids if i in persons_by_id]
        if not persons:
            rids = [int(x) for x in (_pros(el, "roleIds") or "").split(",") if x.strip().isdigit()]
            by_role = {}
            for rid in rids:
                for pp in persons_by_role.get(rid, []):
                    by_role[pp.id] = pp
            persons = list(by_role.values()) or [p.person for p in pos if p.person]
        rate = (sum(_minute_cost(pp) for pp in persons) / len(persons)) if persons else 0.0

        raw_cost = effort * rate
        exp_effort = effort * visit
        exp_cost = exp_effort * rate

        # Deckung: Halten die zugeordneten Personen die benötigten Funktionen/Rollen?
        req_f = [int(x) for x in (_pros(el, "functionIds") or "").split(",") if x.strip().isdigit()]
        req_r = [int(x) for x in (_pros(el, "roleIds") or "").split(",") if x.strip().isdigit()]
        covered_f, covered_r = set(), set()
        for pp in persons:
            covered_r.update(r.id for r in pp.roles)
            covered_f.update(f.id for f in pp.functions)
            for r in pp.roles:
                covered_f.update(f.id for f in r.functions)
        gaps = []
        if (req_f or req_r) and not persons:
            gaps.append("keine Person zugeordnet")
        for fid in req_f:
            if fid not in covered_f:
                gaps.append("Funktion nicht abgedeckt: " + (fn_name.get(fid) or ("#%d" % fid)))
        for rid in req_r:
            if rid not in covered_r:
                gaps.append("Rolle nicht abgedeckt: " + (role_name.get(rid) or ("#%d" % rid)))

        activities.append({
            "id": eid, "name": name, "effort": effort, "visit_factor": visit,
            "raw_cost": raw_cost, "expected_effort": exp_effort, "expected_cost": exp_cost,
            "rate_per_min": rate,
            "legal_basis": _pros(el, "legalBasis") or "",
            "positions": sorted({p.name for p in pos}),   # gleiche Namen nur einmal
            "persons": [{"id": pp.id, "name": pp.name} for pp in persons],
            "req_function_ids": req_f,
            "req_role_ids": req_r,
            "gaps": gaps,
        })
        tot_e += effort
        exp_e += exp_effort
        tot_c += raw_cost
        exp_c += exp_cost

    # ── Subprozesse einrechnen (CallActivity -> anderer Prozess) ──
    pid = getattr(process, "id", None)
    for eid, el in tasks.items():
        if _local(el.tag) != "callActivity":
            continue
        sid = (_pros(el, "subprocessId") or "").strip()
        if not sid.isdigit() or int(sid) in seen:
            continue
        cid = int(sid)
        child = Process.query.filter_by(id=cid).first()
        if child is None or (acc_id is not None and child.account_id != acc_id):
            continue
        child_res = analyze_bpmn(child, _seen=seen | {pid, cid})
        if not child_res["has_model"]:
            continue
        visit = factors.get(eid, 1.0)     # Besuchshäufigkeit der CallActivity
        tot_e += child_res["total_effort"]
        tot_c += child_res["total_cost"]
        exp_e += visit * child_res["expected_effort"]
        exp_c += visit * child_res["expected_cost"]
        label = child.name or "Subprozess"
        for a in child_res["activities"]:
            activities.append({**a,
                               "name": "↳ %s · %s" % (label, a.get("name") or ""),
                               "visit_factor": a["visit_factor"] * visit,
                               "expected_effort": a["expected_effort"] * visit,
                               "expected_cost": a["expected_cost"] * visit,
                               "subprocess": label})

    activities.sort(key=lambda a: (a["name"] or "").lower())
    return {"has_model": True, "activities": activities,
            "total_effort": tot_e, "expected_effort": exp_e,
            "total_cost": tot_c, "expected_cost": exp_c}
