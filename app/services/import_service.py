"""Import eines exportierten Modells (JSON aus export_service) in einen Account.

Legt Organisationen, Einheiten (inkl. Stellen), Rollen, Funktionen und Personen
neu an und bildet die IDs aus dem Export auf die neu erzeugten Datensätze ab
(Relationen bleiben erhalten). Prozesse/BPMN werden NICHT importiert.
"""
from app.models import db, Organization, OrgUnit, Role, Function, Person, Process
from app.services.bpmn_remap import remap_pros_ids


def import_model(account_id, data):
    func_obj, role_obj, org_obj, person_obj, unit_obj = {}, {}, {}, {}, {}
    counts = {"functions": 0, "roles": 0, "organizations": 0, "persons": 0,
              "units": 0, "processes": 0}

    # 1) Funktionen
    for f in data.get("functions", []):
        o = Function(account_id=account_id, name=f.get("name") or "",
                     description=f.get("description"))
        db.session.add(o)
        func_obj[f.get("id")] = o
        counts["functions"] += 1
    db.session.flush()

    # 2) Rollen (mit Funktionen; parent im zweiten Durchgang)
    for r in data.get("roles", []):
        o = Role(account_id=account_id, name=r.get("name") or "")
        o.functions = [func_obj[i] for i in r.get("function_ids", []) if i in func_obj]
        db.session.add(o)
        role_obj[r.get("id")] = o
        counts["roles"] += 1
    db.session.flush()
    for r in data.get("roles", []):
        pid = r.get("parent_id")
        if pid in role_obj:
            role_obj[r.get("id")].parent_id = role_obj[pid].id

    # 3) Organisationen
    for org in data.get("organizations", []):
        oo = Organization(account_id=account_id, name=org.get("name") or "",
                          description=org.get("description"))
        db.session.add(oo)
        org_obj[org.get("id")] = oo
        counts["organizations"] += 1
    db.session.flush()

    # 4) Personen (Organisation/Rollen/Funktionen)
    for p in data.get("persons", []):
        org = org_obj.get(p.get("organization_id"))
        po = Person(account_id=account_id, name=p.get("name") or "",
                    annual_salary=p.get("annual_salary") or 0, fte=p.get("fte") or 0,
                    active=p.get("active", True),
                    organization_id=(org.id if org else None))
        po.roles = [role_obj[i] for i in p.get("role_ids", []) if i in role_obj]
        po.functions = [func_obj[i] for i in p.get("function_ids", []) if i in func_obj]
        db.session.add(po)
        person_obj[p.get("id")] = po
        counts["persons"] += 1
    db.session.flush()

    # 5) Einheiten/Stellen (zwei Durchgänge wegen parent-Selbstbezug)
    for org in data.get("organizations", []):
        for u in org.get("units", []):
            person = person_obj.get(u.get("person_id"))
            uo = OrgUnit(organization_id=org_obj[org.get("id")].id, name=u.get("name") or "",
                         unit_type=u.get("unit_type") or "Team",
                         sort_order=u.get("sort_order") or 0,
                         person_id=(person.id if person else None))
            uo.roles = [role_obj[i] for i in u.get("role_ids", []) if i in role_obj]
            db.session.add(uo)
            unit_obj[u.get("id")] = uo
            counts["units"] += 1
    db.session.flush()
    for org in data.get("organizations", []):
        for u in org.get("units", []):
            pid = u.get("parent_id")
            if pid in unit_obj:
                unit_obj[u.get("id")].parent_id = unit_obj[pid].id
    db.session.flush()

    # 5b) Rollen/Funktionen ihrer Organisation zuordnen (Mandantentrennung).
    #     Genau eine importierte Organisation -> alle zuweisen. Mehrere -> aus der
    #     tatsächlichen Nutzung (Personen/Stellen) eindeutig ableiten; mehrdeutige
    #     bleiben offen und werden ggf. später (Backfill/Dedup) geklärt.
    imported_orgs = list(org_obj.values())
    if len(imported_orgs) == 1:
        only_id = imported_orgs[0].id
        for o in list(func_obj.values()) + list(role_obj.values()):
            o.organization_id = only_id
    else:
        role_orgs, func_orgs = {}, {}
        for p in data.get("persons", []):
            po = person_obj.get(p.get("id"))
            oid = po.organization_id if po else None
            if oid is None:
                continue
            for i in p.get("role_ids", []):
                if i in role_obj:
                    role_orgs.setdefault(role_obj[i], set()).add(oid)
            for i in p.get("function_ids", []):
                if i in func_obj:
                    func_orgs.setdefault(func_obj[i], set()).add(oid)
        for org in data.get("organizations", []):
            oid = org_obj[org.get("id")].id
            for u in org.get("units", []):
                for i in u.get("role_ids", []):
                    if i in role_obj:
                        role_orgs.setdefault(role_obj[i], set()).add(oid)
        for ro, orgs in role_orgs.items():
            if len(orgs) == 1:
                ro.organization_id = next(iter(orgs))
        for fo, orgs in func_orgs.items():
            if len(orgs) == 1:
                fo.organization_id = next(iter(orgs))
    db.session.flush()

    # 6) Prozesse (BPMN ist das führende Modell). Zwei Durchgänge wegen
    #    parent_process- und subprocess-Selbstbezügen. IDs in den pros:-Feldern
    #    werden auf die neu erzeugten Datensätze umgeschrieben.
    id_map = {
        "func": {old: o.id for old, o in func_obj.items()},
        "role": {old: o.id for old, o in role_obj.items()},
        "unit": {old: o.id for old, o in unit_obj.items()},
        "person": {old: o.id for old, o in person_obj.items()},
        "org": {old: o.id for old, o in org_obj.items()},
    }
    proc_obj = {}
    for pr in data.get("processes", []):
        owner = unit_obj.get(pr.get("owner_org_unit_id"))
        po = Process(account_id=account_id, name=pr.get("name") or "",
                     owner_org_unit_id=(owner.id if owner else None))
        db.session.add(po)
        proc_obj[pr.get("id")] = po
        counts["processes"] += 1
    db.session.flush()
    proc_map = {old: o.id for old, o in proc_obj.items()}
    for pr in data.get("processes", []):
        po = proc_obj[pr.get("id")]
        parent = proc_obj.get(pr.get("parent_process_id"))
        if parent is not None:
            po.parent_process_id = parent.id
        xml = (pr.get("bpmn_xml") or "").strip()
        if xml:
            po.bpmn_xml = remap_pros_ids(
                xml, func=id_map["func"], role=id_map["role"], unit=id_map["unit"],
                person=id_map["person"], org=id_map["org"], process=proc_map)

    db.session.commit()
    return counts
