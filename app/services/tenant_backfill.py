"""Backfill: bestehende Rollen/Funktionen einer Organisation (Mandant) zuordnen.

Rollen/Funktionen trugen früher nur account_id (accountweit geteilt). Fürs
Mandanten-Modell braucht jeder Datensatz genau eine Organisation.

Regeln – verlustfrei:
- Account mit genau EINER Organisation: alles dieser Organisation zuordnen.
- Account mit mehreren Organisationen: jede Rolle/Funktion der Organisation
  zuordnen, die sie nutzt (Personen, Stellen, BPMN, und Funktionen zusätzlich
  über die Rollen, die sie enthalten). Wird sie von mehreren Organisationen
  genutzt (echte Teilung), wird sie je nutzender Organisation DUPLIZIERT und
  alle Verweise dieser Organisation auf die Kopie umgehängt – so verliert kein
  Mandant seine Rolle/Funktion, und keiner sieht die des anderen.
- Ungenutzte, nicht zuordenbare Datensätze bleiben offen (nur Gesamtsicht).
"""
import re

from app.models import db, Organization, OrgUnit, Role, Function, Person, Process
from app.services.bpmn_remap import remap_pros_ids


def _csv_ids(xml, attr):
    ids = set()
    for m in re.finditer(r'pros:%s="([^"]*)"' % attr, xml or ""):
        for part in m.group(1).split(","):
            if part.strip().isdigit():
                ids.add(int(part.strip()))
    return ids


def _dedup(objs):
    seen, out = set(), []
    for o in objs:
        if o is not None and o.id not in seen:
            seen.add(o.id)
            out.append(o)
    return out


def backfill_account(account_id):
    orgs = Organization.query.filter_by(account_id=account_id).all()
    if not orgs:
        return 0
    roles = Role.query.filter_by(account_id=account_id).all()
    funcs = Function.query.filter_by(account_id=account_id).all()

    # Häufigster Fall: genau eine Organisation -> alles ihr zuordnen.
    if len(orgs) == 1:
        oid = orgs[0].id
        touched = 0
        for o in roles + funcs:
            if o.organization_id is None:
                o.organization_id = oid
                touched += 1
        db.session.commit()
        return touched

    procs = Process.query.filter_by(account_id=account_id).all()

    # ── Nutzungs-Organisationen je Rolle/Funktion aus tatsächlicher Verwendung ──
    role_using = {r.id: set() for r in roles}
    func_using = {f.id: set() for f in funcs}
    for r in roles:
        for p in r.persons:
            if p.organization_id:
                role_using[r.id].add(p.organization_id)
        for u in r.org_units:
            if u.organization_id:
                role_using[r.id].add(u.organization_id)
    for f in funcs:
        for p in f.persons:
            if p.organization_id:
                func_using[f.id].add(p.organization_id)
    for pr in procs:
        if not pr.organization_id:
            continue
        for rid in _csv_ids(pr.bpmn_xml, "roleIds"):
            if rid in role_using:
                role_using[rid].add(pr.organization_id)
        for fid in _csv_ids(pr.bpmn_xml, "functionIds"):
            if fid in func_using:
                func_using[fid].add(pr.organization_id)
    # Funktionen erben die Nutzung ihrer Rollen (eine Rolle in Org o braucht ihre
    # Funktionen in genau dieser Org).
    for r in roles:
        for f in r.functions:
            if f.id in func_using:
                func_using[f.id] |= role_using[r.id]

    changed = 0
    func_inst, role_inst = {}, {}   # (orig_id, org_id) -> instanz_id

    # ── Funktionen zuordnen/duplizieren ──
    for f in funcs:
        if f.organization_id is not None:
            func_inst[(f.id, f.organization_id)] = f.id
            continue
        using = sorted(func_using.get(f.id) or set())
        if not using:
            continue
        f.organization_id = using[0]
        func_inst[(f.id, using[0])] = f.id
        for oid in using[1:]:
            copy = Function(account_id=account_id, organization_id=oid,
                            name=f.name, description=f.description)
            db.session.add(copy)
            db.session.flush()
            func_inst[(f.id, oid)] = copy.id
            changed += 1

    def _func_for(fid, oid):
        return Function.query.get(func_inst.get((fid, oid), fid))

    # ── Rollen zuordnen/duplizieren (Funktionen je Org auf die Instanz mappen) ──
    for r in roles:
        orig_func_ids = [f.id for f in r.functions]
        if r.organization_id is not None:
            role_inst[(r.id, r.organization_id)] = r.id
            continue
        using = sorted(role_using.get(r.id) or set())
        if not using:
            continue
        r.organization_id = using[0]
        role_inst[(r.id, using[0])] = r.id
        r.functions = _dedup([_func_for(fid, using[0]) for fid in orig_func_ids])
        for oid in using[1:]:
            copy = Role(account_id=account_id, organization_id=oid, name=r.name)
            copy.functions = _dedup([_func_for(fid, oid) for fid in orig_func_ids])
            db.session.add(copy)
            db.session.flush()
            role_inst[(r.id, oid)] = copy.id
            changed += 1

    db.session.flush()

    # ── Verweise je Organisation auf die passende Instanz umhängen ──
    for p in Person.query.filter_by(account_id=account_id).all():
        oid = p.organization_id
        if oid is None:
            continue
        p.roles = _dedup([Role.query.get(role_inst.get((r.id, oid), r.id)) for r in p.roles])
        p.functions = _dedup([Function.query.get(func_inst.get((f.id, oid), f.id)) for f in p.functions])
    for u in (OrgUnit.query.join(Organization)
              .filter(Organization.account_id == account_id).all()):
        oid = u.organization_id
        if oid is None:
            continue
        u.roles = _dedup([Role.query.get(role_inst.get((r.id, oid), r.id)) for r in u.roles])

    # ── BPMN je Prozess-Organisation umschreiben (nur vorhandene IDs, kein Verwerfen) ──
    for pr in procs:
        oid = pr.organization_id
        xml = (pr.bpmn_xml or "").strip()
        if oid is None or not xml:
            continue
        rmap = {rid: role_inst.get((rid, oid), rid) for rid in _csv_ids(xml, "roleIds")}
        fmap = {fid: func_inst.get((fid, oid), fid) for fid in _csv_ids(xml, "functionIds")}
        if rmap or fmap:
            pr.bpmn_xml = remap_pros_ids(xml, role=rmap, func=fmap)

    db.session.commit()
    return changed


def backfill_all():
    total = 0
    rows = db.session.query(Organization.account_id).distinct().all()
    for (acc_id,) in rows:
        if acc_id is not None:
            total += backfill_account(acc_id)
    return total
