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

    passed = sum(1 for c in cases if c["status"] == "passed")
    failed = sum(1 for c in cases if c["status"] in ("failed", "error"))
    print(f"Testprotokoll geschrieben: {args.out} (+ {os.path.basename(html_out)}) — "
          f"{len(cases)} Tests, {passed} bestanden, {failed} fehlgeschlagen, Umgebung {env}")


if __name__ == "__main__":
    main()
