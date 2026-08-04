"""Schreibt die pros:-ID-Referenzen in einem BPMN-XML von alten auf neue IDs um.

Zwei Einsätze:
- Import in einen anderen Account: alle Maps werden übergeben, unbekannte IDs
  verworfen (die Referenz war im Zielaccount nicht vorhanden).
- Duplikat-Bereinigung: nur die betroffenen Maps (z. B. func/role) werden
  übergeben; nicht übergebene Attribute (Map = None) bleiben unverändert.

Rein textuell auf den bekannten, ganzzahligen Attributwerten – kein Parsen von
fremdem XML nötig.
"""
import re


def _remap_csv(value, m):
    out, seen = [], set()
    for part in value.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        new = m.get(int(part))
        if new is None or new in seen:      # unbekannt verwerfen / Duplikate zusammenfassen
            continue
        seen.add(new)
        out.append(str(new))
    return ",".join(out)


def remap_pros_ids(xml, func=None, role=None, unit=None, person=None, org=None, process=None):
    """Gibt das BPMN-XML mit umgeschriebenen pros:-ID-Referenzen zurück.
    Eine Map = None lässt das zugehörige Attribut unangetastet; eine (auch leere)
    Map schreibt um und verwirft dabei unbekannte IDs."""
    def csv_attr(x, attr, m):
        return re.sub(
            r'(pros:%s=")([^"]*)(")' % attr,
            lambda mo: mo.group(1) + _remap_csv(mo.group(2), m) + mo.group(3), x)

    if func is not None:
        xml = csv_attr(xml, "functionIds", func)
    if role is not None:
        xml = csv_attr(xml, "roleIds", role)
    if unit is not None:
        xml = csv_attr(xml, "positionIds", unit)
    if person is not None:
        xml = csv_attr(xml, "personIds", person)

    def single(x, attr, m):
        def repl(mo):
            v = mo.group(2).strip()
            if v.isdigit() and int(v) in m:
                return mo.group(1) + str(m[int(v)]) + mo.group(3)
            return mo.group(1) + mo.group(3)   # unbekannt -> leeren
        return re.sub(r'(pros:%s=")([^"]*)(")' % attr, repl, x)

    if unit is not None:
        xml = single(xml, "orgUnitId", unit)
    if process is not None:
        xml = single(xml, "subprocessId", process)

    if unit is not None or org is not None:
        u, o = unit or {}, org or {}

        def ref(mo):
            v = mo.group(2)
            if v.startswith("unit:") and v[5:].isdigit() and int(v[5:]) in u:
                return mo.group(1) + "unit:" + str(u[int(v[5:])]) + mo.group(3)
            if v.startswith("org:") and v[4:].isdigit() and int(v[4:]) in o:
                return mo.group(1) + "org:" + str(o[int(v[4:])]) + mo.group(3)
            return mo.group(1) + mo.group(3)   # unbekannt -> leeren
        xml = re.sub(r'(pros:orgRef=")([^"]*)(")', ref, xml)

    return xml
