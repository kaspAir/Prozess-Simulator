"""Setzt pros:-Zuordnungsattribute (personIds/functionIds/roleIds) auf einer
bestimmten BPMN-Aktivität.

Rein textuell – so bleiben das nutzererstellte BPMN-XML und vor allem seine
Diagramm-Information (DI) unverändert erhalten (bpmn-js liest den geänderten
XML verlustfrei zurück). Ein erneutes Serialisieren durch einen XML-Parser
würde Präfixe/Reihenfolge umschreiben; das vermeiden wir bewusst – wie schon
in bpmn_remap.py.
"""
import re

PROS_NS = "http://ditwi.ch/bpmn/pros"


def _ensure_pros_namespace(xml):
    """Stellt sicher, dass xmlns:pros im Wurzelelement <…:definitions …> deklariert
    ist – sonst wäre ein neu gesetztes pros:-Attribut nicht wohlgeformt."""
    if "xmlns:pros=" in xml:
        return xml
    m = re.search(r"<(?:\w+:)?definitions\b", xml)
    if not m:
        return xml
    at = m.end()
    return xml[:at] + ' xmlns:pros="%s"' % PROS_NS + xml[at:]


def _find_start_tag(xml, element_id):
    """(start, end) des Start-Tags, dessen id == element_id ist – oder None."""
    for m in re.finditer(r'\bid="([^"]*)"', xml):
        if m.group(1) != element_id:
            continue
        lt = xml.rfind("<", 0, m.start())
        if lt == -1:
            continue
        i, in_quote = m.end(), False
        while i < len(xml):
            ch = xml[i]
            if ch == '"':
                in_quote = not in_quote
            elif ch == ">" and not in_quote:
                return lt, i + 1
            i += 1
    return None


def set_activity_pros(xml, activity_id, **attrs):
    """Setzt/überschreibt pros:-Attribute am Element mit id == activity_id.

    attrs z. B. personIds='1,2', functionIds='', roleIds='3'. Ein leerer Wert
    entfernt das Attribut, ein nicht-leerer setzt bzw. ersetzt es. Gibt
    (neues_xml, gefunden) zurück; bei gefunden=False bleibt das XML unverändert.
    """
    span = _find_start_tag(xml, activity_id)
    if span is None:
        return xml, False
    start, end = span
    tag = xml[start:end]
    self_close = tag.rstrip().endswith("/>")
    core = (tag[:-2] if self_close else tag[:-1]).rstrip()  # ohne '/>' bzw. '>'

    for attr, value in attrs.items():
        core = re.sub(r'\s*pros:%s="[^"]*"' % re.escape(attr), "", core)
        if value:
            core += ' pros:%s="%s"' % (attr, value)

    new_tag = core + (" />" if self_close else ">")
    new_xml = xml[:start] + new_tag + xml[end:]
    if any(attrs.values()):
        new_xml = _ensure_pros_namespace(new_xml)
    return new_xml, True
