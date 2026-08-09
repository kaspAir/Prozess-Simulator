"""Zusammenführen gleichnamiger Rollen und Funktionen eines Accounts.

Mehrfach-Importe legen Rollen/Funktionen additiv an -> gleiche Namen mehrfach mit
verschiedenen IDs. Das verfälscht die Deckungsprüfung (Bedarf zeigt auf Kopie A,
die Person hat Kopie B) und bläht die Organisation auf. Diese Funktion behält je
Name den ältesten Datensatz (kanonisch), hängt ALLE Verweise darauf um
(Rollen->Funktionen, Personen, Stellen, Nodes und die pros:-IDs im BPMN) und
löscht die Dubletten.
"""
from app.models import (
    db, Organization, OrgUnit, Role, Function, Person, Process, Node,
)
from app.services.bpmn_remap import remap_pros_ids


def _canon_map(objs):
    """objs nach id sortiert -> (map old_id->canon_id, {id: obj}, [dubletten])."""
    canon_by_name, id_map, obj_by_id, dups = {}, {}, {}, []
    for o in objs:
        obj_by_id[o.id] = o
        # Schlüssel je Organisation: gleichnamige Rollen/Funktionen/Personen
        # verschiedener Mandanten bleiben getrennt (kein Verschmelzen über Orgs).
        key = (getattr(o, "organization_id", None), (o.name or "").strip().lower())
        if key not in canon_by_name:
            canon_by_name[key] = o
        canon = canon_by_name[key]
        id_map[o.id] = canon.id
        if canon.id != o.id:
            dups.append(o)
    return id_map, obj_by_id, dups


def merge_duplicates(account_id):
    funcs = Function.query.filter_by(account_id=account_id).order_by(Function.id).all()
    roles = Role.query.filter_by(account_id=account_id).order_by(Role.id).all()
    persons = Person.query.filter_by(account_id=account_id).order_by(Person.id).all()
    fmap, fobj, dup_funcs = _canon_map(funcs)
    rmap, robj, dup_roles = _canon_map(roles)
    pmap, pobj, dup_persons = _canon_map(persons)

    def canon(items, m, objs):
        seen, out = set(), []
        for x in items:
            cid = m.get(x.id, x.id)
            if cid not in seen:
                seen.add(cid)
                out.append(objs[cid])
        return out

    def canon_functions(items):
        return canon(items, fmap, fobj)

    def canon_roles(items):
        return canon(items, rmap, robj)

    # Rollen: ihre Funktionen (kanonisch) + parent-Selbstbezug
    for r in roles:
        if r.functions:
            r.functions = canon_functions(r.functions)
        if r.parent_id in rmap:
            r.parent_id = rmap[r.parent_id]
    # Personen: Rollen/Funktionen kanonisieren; Dubletten in die kanonische Person
    # zusammenführen (Vereinigung der Rollen/Funktionen).
    for p in persons:
        if p.roles:
            p.roles = canon_roles(p.roles)
        if p.functions:
            p.functions = canon_functions(p.functions)
    for d in dup_persons:
        c = pobj[pmap[d.id]]
        c.roles = canon_roles(list(c.roles) + list(d.roles))
        c.functions = canon_functions(list(c.functions) + list(d.functions))
    # Stellen/Einheiten: Rollen kanonisch + person_id auf kanonische Person
    for u in (OrgUnit.query.join(Organization)
              .filter(Organization.account_id == account_id).all()):
        if u.roles:
            u.roles = canon_roles(u.roles)
        if u.person_id in pmap:
            u.person_id = pmap[u.person_id]
    # Nodes (altes Modell): Rollen + benötigte Funktionen
    for n in (Node.query.join(Process, Node.process_id == Process.id)
              .filter(Process.account_id == account_id).all()):
        if n.roles:
            n.roles = canon_roles(n.roles)
        if n.required_functions:
            n.required_functions = canon_functions(n.required_functions)
    db.session.flush()

    # BPMN-Modelle: pros:functionIds/roleIds/personIds auf die kanonischen IDs
    for pr in Process.query.filter_by(account_id=account_id).all():
        xml = (pr.bpmn_xml or "").strip()
        if xml:
            pr.bpmn_xml = remap_pros_ids(xml, func=fmap, role=rmap, person=pmap)

    for o in dup_funcs + dup_roles + dup_persons:
        db.session.delete(o)
    db.session.commit()
    return {"functions_merged": len(dup_funcs), "roles_merged": len(dup_roles),
            "persons_merged": len(dup_persons)}
