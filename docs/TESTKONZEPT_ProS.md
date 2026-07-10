# Testkonzept – Prozess-Simulator (Lean)

Schlanke Übertragung des produktübergreifenden Testkonzepts (Zielarchitektur V0.1)
auf den Prozess-Simulator. Ausführliche Fassung als Word-Dokument: siehe
`Testkonzept_ProS_*.docx`.

**Leitmotiv:** Getestet wird, um einen *nachvollziehbaren Nachweis* zu erzeugen.
Jeder Testlauf produziert ein reproduzierbares, versioniertes **Testprotokoll**.
Auf «ist das getestet?» antwortet ein Dokument, kein «ja».

## Umgebungen und Testbetrieb

| Umgebung | Port / Domain | Wer testet | Was läuft |
|----------|---------------|------------|-----------|
| dev | – (nur CI) | Entwickler | schnelle deterministische Suite + statische Analyse |
| test | 8011 / test.ditwi.ch | Team, intern explorativ | Suite + Deploy + Smoke |
| int | 8012 / int.ditwi.ch | **Kunde** (explorativ + Abnahme) | zwei Phasen mit internem Tor |
| prod | 8010 / ditwi.ch | Produktivbetrieb | nur nicht-destruktive Smoke-/Health-Checks |

## Kalibrierte CI (Jenkins)

- **Bei jedem Build:** schnelle deterministische Suite (`pytest`) + statische Analyse.
- **Gestufter TC-Katalog:** Fälle mit dem Marker `teststufe` (`tests/test_teststufe_tc.py`,
  TC-001..025 aus «Testfälle DigiTwin») laufen **nicht auf dev**, sondern erst ab
  **test**. Steuerung: dev fährt `pytest -m "not teststufe"`, test/int/main die volle
  Suite. Noch nicht automatisierbare TCs (fehlende Funktion / kein Orakel) sind als
  `skip` mit Begründung markiert und erscheinen transparent als «übersprungen».
- **Nach Deploy (test/int/main):** nicht-destruktiver Health-Check auf `/health`.
- **Schwere Suiten** (Systemintegration, Last, dynamische Sicherheit): erst wenn echte
  Umsysteme existieren – dann auf Promotion/geplant, nicht pro Commit.

Jeder Lauf erzeugt dasselbe Artefakt: das **Testprotokoll**.

## Das Testprotokoll

`scripts/gen_test_protocol.py` erzeugt aus dem JUnit-XML von pytest deterministisch
ein lesbares Protokoll (`reports/test-protocol.md` + `.html`), das Jenkins archiviert.
Es weist aus: Umgebung, Commit, Zeit, Gesamtergebnis und **je Testart** die Zahlen –
inklusive **Schnittstellenmodus** (`mock`/`real`).

- Format **JUnit-XML** ist bewusst gewählt: XRay/Zephyr können es später nativ
  importieren (Einweg-Projektion nach Jira, wenn diese Schnittstelle kommt).
- Die Spalten *Testart* und *Schnittstellenmodus* existieren schon, obwohl heute
  alles «gegen die eigene DB» (= `mock`) läuft. Sobald echte Umsysteme kommen
  (z. B. Organigramm-/Prozess-Import), werden die Zeilen *Kontrakt* und
  *Systemintegration* ehrlich ergänzt – ohne Neubau.

## Testarten und ihre Zuordnung

Die Zuordnung Testmodul → Testart liegt als Konfiguration in
`scripts/test_classification.py` (heute pytest-basiert). Aktueller Stand:

| Modul | Testart | Schnittstelle |
|-------|---------|---------------|
| `test_teststufe_tc` | Fachliche Testfälle (TC-Katalog, **ab test**) | mock |
| `test_functional_*` | Fachliche Testfälle | mock |
| `test_domain` | Fachliche Testfälle | mock |
| `test_auth` | Komponententest | mock |
| `test_smoke` | Smoke / Komponententest | mock |

## Fachliche Testfälle (wachsende Sammlung)

`tests/test_functional_process.py` ist das Muster: *einen Prozess erfassen und
Nodes darin anlegen* – deterministisch über den Test-Client. Solche Fälle wachsen
mit dem Produkt. Später können sie YAML-deklariert oder **agent-generiert** entstehen;
die **Ausführung und das Pass/Fail-Urteil bleiben immer deterministisch** (Test-Runner
entscheidet, nie ein Agent). Ein agent-gefundener Fall wird zuerst als konkreter
Regressionsfall eingefroren und menschlich freigegeben, bevor er in die Suite wandert.

## Das Zwei-Phasen-Tor auf int

Weil der Kunde auf **int** testet:

1. **Phase 1 (intern):** Deploy auf int → Suite + Health-Check → Protokoll archiviert.
2. **Tor:** dokumentierte **interne Freigabe**, sobald das Protokoll grün ist.
3. **Phase 2 (Kunde):** exploratives Testen + Abnahme.

**Rücksprung:** Wird in Phase 2 ein Fehler behoben, laufen mindestens die betroffenen
internen Tests erneut grün, bevor Phase 2 fortgesetzt wird.

## Statische Sicherheit (in der CI, advisory)

Stufe dev: `ruff` (Linter), `bandit` (Python-SAST), `pip-audit` (Abhängigkeits-CVEs).
Die Reports werden archiviert; sie brechen den Build vorerst **nicht** ab
(können später scharf geschaltet werden).

## Lokal ausführen

```bash
pip install -r tests/requirements.txt
mkdir -p reports
pytest tests/ -v --junitxml=reports/junit.xml
python scripts/gen_test_protocol.py --junit reports/junit.xml \
    --out reports/test-protocol.md --job lokal --commit "$(git rev-parse --short HEAD)"
# optional:
ruff check app scripts run.py
bandit -r app
pip-audit -r requirements.txt
```

## Nicht-Ziele (bewusst)

- Kein Testbetrieb in prod (nur Smoke/Health).
- Kein Agent entscheidet über Pass/Fail.
- Kein Kundenzugriff auf int vor grüner, protokollierter interner Freigabe.
- Keine echte Systemintegration/Last/Pentest/KI, solange kein echtes Umsystem bzw.
  der KI-Backlogpunkt (B-29) vorliegt.
- ProS übernimmt die Bausteine nur für den **eigenen** Nutzen, ist nicht das
  Testbett für das geteilte Suite-Werkzeug.
