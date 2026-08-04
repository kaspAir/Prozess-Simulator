"""Node/Edge-Prozessmodell -> BPMN-2.0-XML (mit pros:-Attributen und Diagramm).

Migrationsbaustein: das alte, vereinfachte Prozessmodell (Node/Edge) wird in ein
vollständiges BPMN-Modell übersetzt, das der bpmn-js-Editor öffnen kann. Damit
wird BPMN das einzige Prozessmodell (das Node-Modell wird abgelöst).

Nur Serialisierung (String-Aufbau mit Escaping) – kein Parsen von fremdem XML.
"""
from xml.sax.saxutils import escape  # nosec B406 - nur Ausgabe-Escaping, kein Parsen

PROS_NS = "http://ditwi.ch/bpmn/pros"

# BPMN-Elementtyp und Shape-Grösse je Node-Typ des alten Modells.
_KIND = {
    "start": ("startEvent", 36, 36),
    "end": ("endEvent", 36, 36),
    "xor": ("exclusiveGateway", 50, 50),
    "subprocess": ("callActivity", 100, 80),
    "task": ("task", 100, 80),
}


def _a(v):
    """Escape für einen Attributwert (in doppelten Anführungszeichen)."""
    return escape("" if v is None else str(v), {'"': "&quot;", "\n": "&#10;"})


def _csv(ids):
    return ",".join(str(i) for i in ids)


def _kind(node):
    return _KIND.get(node.type, _KIND["task"])


def node_to_bpmn(process):
    """Erzeugt BPMN-2.0-XML für einen Prozess aus seinen Nodes/Edges."""
    nodes = sorted(process.nodes, key=lambda n: (n.sort_order, n.id))

    # Kanten sammeln (aus den ausgehenden Kanten jedes Nodes)
    edges = []
    for n in nodes:
        for e in (n.outgoing_edges or []):
            edges.append(e)
    edges.sort(key=lambda e: e.id)

    nid = lambda n: f"Node_{n.id}"        # noqa: E731
    fid = lambda e: f"Flow_{e.id}"        # noqa: E731

    incoming, outgoing = {}, {}
    for e in edges:
        outgoing.setdefault(e.source_node_id, []).append(e)
        incoming.setdefault(e.target_node_id, []).append(e)

    proc_id = f"Process_{process.id}"
    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append(
        '<bpmn:definitions '
        'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
        'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
        'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
        f'xmlns:pros="{PROS_NS}" '
        f'id="Definitions_{process.id}" targetNamespace="http://ditwi.ch/bpmn">')
    out.append(f'  <bpmn:process id="{proc_id}" isExecutable="false">')

    # Fallback: leerer Prozess -> ein Start-Ereignis, damit der Editor etwas zeigt.
    if not nodes:
        out.append('    <bpmn:startEvent id="StartEvent_1" name="Start" />')

    for n in nodes:
        tag, w, h = _kind(n)
        attrs = [f'id="{nid(n)}"', f'name="{_a(n.name)}"']
        if n.type in ("task", "subprocess"):
            if n.effort_minutes:
                attrs.append(f'pros:effortMinutes="{_a(n.effort_minutes)}"')
            if n.legal_basis:
                attrs.append(f'pros:legalBasis="{_a(n.legal_basis)}"')
            fids = [f.id for f in n.required_functions]
            rids = [r.id for r in n.roles]
            pids = [p.id for p in n.assigned_positions]
            if fids:
                attrs.append(f'pros:functionIds="{_csv(fids)}"')
            if rids:
                attrs.append(f'pros:roleIds="{_csv(rids)}"')
            if pids:
                attrs.append(f'pros:positionIds="{_csv(pids)}"')
        if n.type == "subprocess" and n.subprocess_id:
            attrs.append(f'pros:subprocessId="{_a(n.subprocess_id)}"')
        children = []
        for e in incoming.get(n.id, []):
            children.append(f'      <bpmn:incoming>{fid(e)}</bpmn:incoming>')
        for e in outgoing.get(n.id, []):
            children.append(f'      <bpmn:outgoing>{fid(e)}</bpmn:outgoing>')
        if children:
            out.append(f'    <bpmn:{tag} {" ".join(attrs)}>')
            out.extend(children)
            out.append(f'    </bpmn:{tag}>')
        else:
            out.append(f'    <bpmn:{tag} {" ".join(attrs)} />')

    for e in edges:
        fattrs = [f'id="{fid(e)}"',
                  f'sourceRef="Node_{e.source_node_id}"',
                  f'targetRef="Node_{e.target_node_id}"']
        if e.condition:
            fattrs.append(f'name="{_a(e.condition)}"')
        if e.probability_percent is not None:
            fattrs.append(f'pros:probability="{_a(int(round(e.probability_percent)))}"')
        out.append(f'    <bpmn:sequenceFlow {" ".join(fattrs)} />')

    out.append('  </bpmn:process>')

    # ── Diagramm (BPMN DI) aus den gespeicherten Koordinaten ──
    bounds = {}
    for n in nodes:
        _, w, h = _kind(n)
        bounds[n.id] = (float(n.x or 0), float(n.y or 0), w, h)

    out.append('  <bpmndi:BPMNDiagram id="Diagram_1">')
    out.append(f'    <bpmndi:BPMNPlane id="Plane_1" bpmnElement="{proc_id}">')
    if not nodes:
        out.append('      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">'
                   '<dc:Bounds x="150" y="100" width="36" height="36" /></bpmndi:BPMNShape>')
    for n in nodes:
        x, y, w, h = bounds[n.id]
        out.append(
            f'      <bpmndi:BPMNShape id="{nid(n)}_di" bpmnElement="{nid(n)}">'
            f'<dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" />'
            '</bpmndi:BPMNShape>')
    for e in edges:
        s = bounds.get(e.source_node_id)
        t = bounds.get(e.target_node_id)
        if not s or not t:
            continue
        sx, sy, sw, sh = s
        tx, ty, tw, th = t
        p1 = (sx + sw, sy + sh / 2)          # rechte Mitte der Quelle
        p2 = (tx, ty + th / 2)               # linke Mitte des Ziels
        out.append(
            f'      <bpmndi:BPMNEdge id="{fid(e)}_di" bpmnElement="{fid(e)}">'
            f'<di:waypoint x="{p1[0]:.0f}" y="{p1[1]:.0f}" />'
            f'<di:waypoint x="{p2[0]:.0f}" y="{p2[1]:.0f}" />'
            '</bpmndi:BPMNEdge>')
    out.append('    </bpmndi:BPMNPlane>')
    out.append('  </bpmndi:BPMNDiagram>')
    out.append('</bpmn:definitions>')
    return "\n".join(out)
