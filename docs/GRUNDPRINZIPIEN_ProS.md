# Grundprinzipien Prozess-Simulator

Diese vier Prinzipien sind die **Basis für alles** im Prozess-Simulator (ProS).
Jede Funktion, jeder Entscheid und jede Freigabe wird an ihnen gemessen.

## 1. Rechtssicherheit gewährleisten
Fachliche Aussagen und Ergebnisse müssen belastbar und regelkonform sein.
- Keine erfundenen Fakten/Fundstellen; im Zweifel Feld leer lassen.
- Deterministischer Kern entscheidet über Ergebnisse – nie ein Sprachmodell.
- Verbindliche fachliche Regeln explizit und geprüft (z. B. Validierungen).

## 2. Nachvollziehbarkeit sicherstellen
Herkunft, Weg und Ergebnis müssen jederzeit rekonstruierbar sein.
- **Testprotokoll als Nachweis** (versioniert, mit Umgebung, Commit, Ergebnis je
  Testfall) – „ist das getestet?" → ein auditierbares Dokument.
- Änderungen über die Freigabekette dev → test → int → prod, mit Toren.
- Alles code-/git-versioniert und diffbar; kein Wissen nur in flüchtigen Tools.

## 3. Datenschutz & Informationssicherheit
Schutz sensibler Daten ist nicht verhandelbar.
- **Statische Sicherheit blockierend** in der CI (ruff, bandit, pip-audit);
  Abhängigkeits-CVEs werden zeitnah behoben.
- Login-Wall + mandantenfähiges RBAC; sensible Felder nur für Berechtigte.
- Datenresidenz beachten; externe Abhängigkeiten (z. B. Web-Fonts) kritisch prüfen
  und für Produktion nach Möglichkeit self-hosten.

## 4. Datenqualität prüfen und sicherstellen
Nur saubere Daten liefern belastbare Analysen und Simulationen.
- Eingabevalidierung (FTE 0–1, keine Negativwerte, konsistente Modelle).
- Fachliche Testfälle (TC-Katalog) prüfen die korrekte Erfassung und Auswertung.
- Export (JSON/XML) für externe Kontrolle und Weiterverarbeitung der Modelldaten.

---

Bezug: Diese Prinzipien decken sich mit dem Testkonzept (`docs/TESTKONZEPT_ProS.md`)
und der Freigabekette. Sie gelten produktweit und sind bei jedem neuen Feature –
auch beim geplanten BPMN-Werkzeug – einzuhalten.
