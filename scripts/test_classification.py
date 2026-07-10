"""Zuordnung Testmodul/Testname -> Testart (Konfiguration vor Programmierung).

Heute pytest-basiert; die Zuordnung erfolgt anhand des Modul-/Klassennamens.
Bewusst als leicht editierbare Konfiguration gehalten: Sobald es YAML- oder
Agent-generierte Testfaelle gibt (siehe docs/TESTKONZEPT_ProS.md), tragen diese
ihre Testart selbst und speisen dasselbe Protokoll.

Alle Faelle laufen heute gegen die eigene DB -> Schnittstellenmodus 'mock'.
Echte Systemintegration (Schnittstellenmodus 'real') entsteht erst mit echten
Umsystemen (z. B. Organigramm-/Prozess-Import).
"""

# Reihenfolge = Prioritaet: erste passende Regel gewinnt. Teilstring-Match (lower).
CLASSIFICATION = [
    ("test_teststufe",  "Fachliche Testfälle (TC-Katalog, ab test)"),
    ("test_functional", "Fachliche Testfälle"),
    ("test_domain",     "Fachliche Testfälle"),
    ("test_auth",       "Komponententest"),
    ("test_smoke",      "Smoke / Komponententest"),
]
DEFAULT_TESTART = "Komponententest"

# Heute gegen die eigene DB. Bei echten Umsystemen pro Testart auf 'real' heben.
SCHNITTSTELLENMODUS = "mock"


def classify(nodeid_or_classname):
    s = (nodeid_or_classname or "").lower()
    for needle, art in CLASSIFICATION:
        if needle in s:
            return art
    return DEFAULT_TESTART
