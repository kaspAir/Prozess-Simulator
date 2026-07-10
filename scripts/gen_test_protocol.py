"""Erzeugt aus einem JUnit-XML (pytest) ein reproduzierbares, lesbares Testprotokoll.

Deterministisch: der Inhalt wird ausschliesslich aus dem Testergebnis abgeleitet,
nichts wird frei interpretiert (vgl. Testkonzept, Prinzip «Protokoll als Nachweis»).
Ausgabe: Markdown (--out) und daneben eine .html-Fassung.

Aufruf (in der CI):
    python scripts/gen_test_protocol.py \
        --junit reports/junit.xml --out reports/test-protocol.md \
        --job "$JOB_NAME" --commit "$GIT_COMMIT"
"""
import argparse
import html
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_classification as tc  # noqa: E402

ENV_FROM_JOB = [("main", "prod"), ("integration", "int"), ("test", "test"), ("dev", "dev")]


def derive_env(job):
    j = (job or "").lower()
    for needle, env in ENV_FROM_JOB:
        if needle in j:
            return env
    return job or "lokal"


def parse_junit(path):
    """Liest alle <testcase>-Elemente ein und bestimmt je Fall den Status."""
    cases = []
    if not os.path.exists(path):
        return cases, 0.0
    tree = ET.parse(path)
    root = tree.getroot()
    total_time = 0.0
    for tsuite in root.iter("testsuite"):
        try:
            total_time = max(total_time, float(tsuite.get("time") or 0))
        except ValueError:
            pass
    for case in root.iter("testcase"):
        classname = case.get("classname") or ""
        name = case.get("name") or ""
        status = "passed"
        message = ""
        for child in case:
            tag = child.tag.lower()
            if tag == "failure":
                status = "failed"
                message = (child.get("message") or "").strip()
            elif tag == "error":
                status = "error"
                message = (child.get("message") or "").strip()
            elif tag == "skipped":
                status = "skipped"
                message = (child.get("message") or "").strip()
        cases.append({
            "classname": classname,
            "name": name,
            "status": status,
            "message": message,
            "testart": tc.classify(classname + "." + name),
        })
    return cases, total_time


def aggregate(cases):
    """Aggregiert je Testart: gesamt / bestanden / fehlgeschlagen / übersprungen."""
    by_art = {}
    for c in cases:
        a = by_art.setdefault(c["testart"], {"total": 0, "passed": 0, "failed": 0, "skipped": 0})
        a["total"] += 1
        if c["status"] == "passed":
            a["passed"] += 1
        elif c["status"] == "skipped":
            a["skipped"] += 1
        else:
            a["failed"] += 1
    return by_art


def build_markdown(cases, total_time, env, commit, job):
    total = len(cases)
    passed = sum(1 for c in cases if c["status"] == "passed")
    skipped = sum(1 for c in cases if c["status"] == "skipped")
    failed = total - passed - skipped
    overall = "🟢 GRÜN" if failed == 0 and total > 0 else ("🔴 ROT" if total > 0 else "⚪ KEINE TESTS")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    lines = []
    lines.append("# Testprotokoll – Prozess-Simulator")
    lines.append("")
    lines.append("| Feld | Wert |")
    lines.append("|------|------|")
    lines.append(f"| Umgebung | {env} |")
    lines.append(f"| Job | {job or '—'} |")
    lines.append(f"| Commit | {commit or '—'} |")
    lines.append(f"| Zeitpunkt (UTC) | {now} |")
    lines.append(f"| Gesamtergebnis | **{overall}** |")
    lines.append(f"| Tests gesamt | {total} (bestanden {passed}, fehlgeschlagen {failed}, übersprungen {skipped}) |")
    lines.append(f"| Dauer | {total_time:.2f} s |")
    lines.append("")
    lines.append("## Ergebnis je Testart")
    lines.append("")
    lines.append("| Testart | Schnittstelle | Gesamt | Bestanden | Fehlgeschlagen | Übersprungen |")
    lines.append("|---------|---------------|-------:|----------:|---------------:|-------------:|")
    for art in sorted(aggregate(cases)):
        a = aggregate(cases)[art]
        lines.append(f"| {art} | {tc.SCHNITTSTELLENMODUS} | {a['total']} | {a['passed']} | "
                     f"{a['failed']} | {a['skipped']} |")
    lines.append("")

    fails = [c for c in cases if c["status"] in ("failed", "error")]
    if fails:
        lines.append("## Fehlgeschlagene Tests")
        lines.append("")
        for c in fails:
            msg = c["message"].splitlines()[0] if c["message"] else ""
            lines.append(f"- **{c['classname']}::{c['name']}** — {msg}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Deterministisch erzeugt aus dem JUnit-XML des pytest-Laufs. "
                 "Der Schnittstellenmodus «mock» bedeutet: geprüft gegen die eigene Datenbank, "
                 "nicht gegen ein echtes Umsystem._")
    return "\n".join(lines) + "\n"


def build_pdf(path, cases, total_time, env, commit, job):
    """Erzeugt ein vorzeigbares PDF-Testprotokoll (ReportLab, reine Python-Lib).
    Gibt True zurück, wenn erstellt; False, wenn ReportLab fehlt (dann nur MD/HTML)."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)
    except ImportError:
        return False

    total = len(cases)
    passed = sum(1 for c in cases if c["status"] == "passed")
    skipped = sum(1 for c in cases if c["status"] == "skipped")
    failed = total - passed - skipped
    green = failed == 0 and total > 0
    overall = "GRÜN" if green else ("ROT" if total > 0 else "KEINE TESTS")
    result_color = colors.HexColor("#0b6b3a") if green else colors.HexColor("#b00020")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18,
                        textColor=colors.HexColor("#27324a"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12,
                        textColor=colors.HexColor("#27324a"), spaceBefore=12)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8.5,
                           textColor=colors.HexColor("#555b66"))
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=9)

    doc = SimpleDocTemplate(path, pagesize=A4, title="Testprotokoll – Prozess-Simulator",
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    story = []
    story.append(Paragraph("Testprotokoll – Prozess-Simulator", h1))
    story.append(Paragraph(
        "Reproduzierbarer Nachweis eines Testlaufs – deterministisch aus dem "
        "pytest-Ergebnis erzeugt.", small))
    story.append(Spacer(1, 8 * mm))

    meta = [
        ["Umgebung", env],
        ["Job", job or "—"],
        ["Commit", commit or "—"],
        ["Zeitpunkt (UTC)", now],
        ["Gesamtergebnis", overall],
        ["Tests gesamt", f"{total}  (bestanden {passed}, fehlgeschlagen {failed}, "
                         f"übersprungen {skipped})"],
        ["Dauer", f"{total_time:.2f} s"],
    ]
    mt = Table(meta, colWidths=[42 * mm, 128 * mm])
    mt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#315bdc")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 4), (1, 4), result_color),
        ("FONTNAME", (1, 4), (1, 4), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e0e5ef")),
    ]))
    story.append(mt)

    story.append(Paragraph("Ergebnis je Testart", h2))
    head = ["Testart", "Schnittstelle", "Gesamt", "Bestanden", "Fehlgeschl.", "Überspr."]
    data = [head]
    agg = aggregate(cases)
    for art in sorted(agg):
        a = agg[art]
        data.append([art, tc.SCHNITTSTELLENMODUS, str(a["total"]), str(a["passed"]),
                     str(a["failed"]), str(a["skipped"])])
    at = Table(data, colWidths=[55 * mm, 25 * mm, 20 * mm, 24 * mm, 24 * mm, 22 * mm])
    at.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#315bdc")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fb")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d6def0")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(at)

    fails = [c for c in cases if c["status"] in ("failed", "error")]
    if fails:
        story.append(Paragraph("Fehlgeschlagene Tests", h2))
        for c in fails:
            msg = c["message"].splitlines()[0] if c["message"] else ""
            txt = f"<b>{esc(c['classname'])}::{esc(c['name'])}</b> — {esc(msg)}"
            story.append(Paragraph(txt, cell))
            story.append(Spacer(1, 1.5 * mm))

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "Schnittstellenmodus «mock»: geprüft gegen die eigene Datenbank, nicht gegen ein "
        "echtes Umsystem. Erzeugt vom deterministischen Test-Runner – der Inhalt stammt "
        "ausschliesslich aus dem Testergebnis.", small))

    doc.build(story)
    return True


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markdown_to_html(md):
    body = html.escape(md)
    return (
        "<!doctype html><html lang='de'><head><meta charset='utf-8'>"
        "<title>Testprotokoll – Prozess-Simulator</title>"
        "<style>body{font-family:system-ui,Arial,sans-serif;max-width:900px;margin:2rem auto;"
        "padding:0 1rem;color:#1d2433}pre{white-space:pre-wrap;font-size:14px;line-height:1.5}</style>"
        "</head><body><pre>" + body + "</pre></body></html>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--junit", default="reports/junit.xml")
    ap.add_argument("--out", default="reports/test-protocol.md")
    ap.add_argument("--job", default=os.getenv("JOB_NAME", ""))
    ap.add_argument("--commit", default=os.getenv("GIT_COMMIT", ""))
    args = ap.parse_args()

    cases, total_time = parse_junit(args.junit)
    env = derive_env(args.job)
    md = build_markdown(cases, total_time, env, args.commit, args.job)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    html_out = os.path.splitext(args.out)[0] + ".html"
    with open(html_out, "w", encoding="utf-8") as f:
        f.write(markdown_to_html(md))

    pdf_out = os.path.splitext(args.out)[0] + ".pdf"
    pdf_ok = build_pdf(pdf_out, cases, total_time, env, args.commit, args.job)

    passed = sum(1 for c in cases if c["status"] == "passed")
    failed = sum(1 for c in cases if c["status"] in ("failed", "error"))
    outputs = os.path.basename(html_out) + (", " + os.path.basename(pdf_out) if pdf_ok else "")
    print(f"Testprotokoll geschrieben: {args.out} (+ {outputs}) — "
          f"{len(cases)} Tests, {passed} bestanden, {failed} fehlgeschlagen, Umgebung {env}")
    if not pdf_ok:
        print("Hinweis: ReportLab nicht installiert -> kein PDF erzeugt (nur MD/HTML).")


if __name__ == "__main__":
    main()
