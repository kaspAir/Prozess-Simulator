<!-- erzeugt-aus: _docs/5_Entwicklung/richtlinien -->

# Entwicklungsrichtlinien — Prozess-Simulator

> **Diese Datei wird erzeugt. Hier nicht bearbeiten.**
> Quelle: `C:\Projekte\Skills\_docs\5_Entwicklung\richtlinien`
> Projektdatei: `projekte/Prozess-Simulator.yaml` · Stand der Quellen: 2026-08-02
> Neu bauen: `python _tools/richtlinien_bauen.py Prozess-Simulator`

Module: `datenmodell`, `mandantentrennung`, `oberflaeche`, `tests-und-nachweis`, `betrieb`

---
# Entwicklungsrichtlinien — Basis

Gilt für **jedes** Repository der Suite. Modulunabhängig, immer eingebunden.

> Wertvoll sind nicht Stilregeln, sondern Projektwahrheiten aus konkreten
> Fehlschlägen. Was hier steht, hat einmal Geld oder einen Lauf gekostet.

---

## 1 · Die Norm ist Eingabe

Architektur, Manifeste, Capability-Katalog, Testkonzept und Bedienungsnorm werden
**angewendet, nicht geändert**. Wer beim Bauen merkt, dass eine Norm nicht trägt,
meldet das zurück — er baut nicht darum herum.

- Eine Abweichung von der Spezifikation ist ein **Rückgabegrund**, kein
  Implementierungsdetail.
- Trägt ein Architekturentscheid nicht, geht das an die Architektur. Fehlt ein
  Baustein, geht das an den Katalog. Lässt sich ein Manifestsatz nicht in eine
  Regel übersetzen, ist das ein Befund am Manifest — nicht an der Umsetzung.
- **Kein stilles Abweichen.** Jede Abweichung steht im Konformitätsnachweis.

## 2 · Die acht Projektwahrheiten

| Regel | Woher sie kommt |
|---|---|
| **Das Modell erzeugt keine autoritativen Fakten.** Es darf klassifizieren, synthetisieren, routen und interpretieren — Fundstellen und Nachweise stammen aus verifizierbaren Quellen. | Architekturkonzept |
| **Governance-Zusagen deterministisch erzwingen, nicht promptseitig erbitten.** Eine Rückstufung ist einseitig: ein strengeres Urteil wird nie abgemildert. | Stufe 4 |
| **Dem Modell die Gelegenheit entziehen, statt die Regel zu erklären.** Soll etwas nicht wiederholt werden, gibt man ihm den Text gar nicht erst. | Stufe 4 |
| **Zahlen zählt der Code, nicht das Modell.** | Stufe 4, zweiter Lauf |
| **Kein Anbietername in einer Norm.** Anbieterspezifisches lebt im Adapter. | Rahmenwerk, Kap. 7 |
| **Keine geratenen Grenzen.** Obergrenzen, Deckel und Budgets werden zur Laufzeit aus gemessenen Grössen berechnet, nicht als Konstante gesetzt. | Betrieb |
| **DOCX: Zellen in `w:sdt` gehören zur Zeile** — `python-docx` überspringt sie. | Prototyp-Prüfer |
| **DOCX: Word zerlegt Text in Runs** — ohne Trennzeichen verbinden. | Prototyp-Prüfer |

## 3 · Der Negativraum

Zehn Verbote der Referenzarchitektur. Sie sind der prüfbarste Teil, weil Verstösse
konkret sind. **Ein Befund, der sich darauf beruft, nennt die Kennung** — ohne
Kennung ist es eine Behauptung.

| Kennung | Ein Werkzeug darf nicht … | Prinzip |
|---|---|---|
| `NR-01` | eine Entscheidung treffen, die einem Menschen zusteht — auch nicht durch Voreinstellung, stille Automatik oder eine vorausgefüllte Wahrheit. | `RA-01` |
| `NR-02` | eine Fundstelle, eine Zahl oder einen Beleg erzeugen, der nicht aus einer Quelle stammt. | `RA-02` |
| `NR-03` | ein Modell direkt ansprechen. | `RA-09` |
| `NR-04` | eine Mandantengrenze überschreiten — lesend, schreibend oder als Vorlage. | `RA-08` |
| `NR-05` | einen freigegebenen Zustand behalten, während sich der Inhalt ändert. | `RA-05` |
| `NR-06` | ein kontrolliertes Vokabular eigenmächtig erweitern. | `RA-12` |
| `NR-07` | ein Ergebnis ohne Herkunft ausgeben. | `RA-10` |
| `NR-08` | eine Zusicherung allein durch Anweisung an ein Modell sicherstellen. | `RA-01` |
| `NR-09` | die Bedeutung gespeicherter Werte ändern, ohne den Übergang festzuhalten. | `RA-06` |
| `NR-10` | einen ausgestellten Nachweis nachträglich bearbeiten. | `RA-06`, `RA-13` |

## 4 · Kennungen

Wo eine Regel eine Kennung hat, wird sie genannt — in Befunden, Kommentaren,
Rückgaben und Tests. **Eine Kennung wird nie umgewidmet:** Neues wird angehängt,
Zurückgezogenes behält seine Nummer, eine wesentliche Inhaltsänderung ist eine neue
Nummer.

`RA-01`…`RA-13` Architektur · `NR-01`…`NR-10` Negativraum · `SK-01`…`SK-17`
Skill-Norm · `D-…` Invarianten · `ADR-T…` Testentscheide ·
`PH`·`WA`·`GE`·`SC`·`EN` Manifestsätze.

## 5 · Namen

Nach aussen trägt ein Produkt **genau einen** Namen — den aus seiner
Werkzeugarchitektur. Interne Arbeitsnamen erscheinen nicht in Dokumenten,
Oberflächen, Log-Ausgaben, API-Antworten, Klassennamen oder Dateinamen. Wo
Altlasten bestehen, werden sie bei der nächsten Berührung bereinigt; eine
Umbenennung von Umgebungsvariablen ist ein Bruch und wird abgestimmt.

## 6 · Was beim Menschen bleibt

Die Normen setzen · Abweichungen beurteilen · über Kataloganträge und über
Manifestsätze ohne Regel entscheiden · Ground-Truth sein. Was fachlich richtig ist,
kann kein Agent aus sich selbst bestimmen.

---

## Datenmodell und Zustände

Gilt, sobald das Werkzeug eigene Kernobjekte führt.

**Governance-Mixin an jedem Kernobjekt** (`RA-03`). Zu jedem Objekt lässt sich
beantworten: wer hat es wann in welchen Zustand gebracht, und worauf stützt es sich.
Mindestens `created_at` · `updated_at` · `version` · `created_by` · `status`.

**Entwurf und Bestätigung sind getrennte Felder** (`RA-04`). Nicht ein Feld mit
zwei Bedeutungen und nicht ein Flag daneben. Ein Vorschlag des Modells darf nie an
derselben Stelle stehen wie eine menschliche Bestätigung — sonst ist später nicht
mehr feststellbar, was jemand tatsächlich verantwortet hat.

**Freigabe ist ein Tor** (`RA-05`). Ändert sich der Inhalt, wird die Freigabe
ungültig — automatisch, nicht auf Zuruf (`NR-05`). Wer den Zustand behält und den
Inhalt ändert, hat die Freigabe zu einer Behauptung gemacht.

**Änderungen sind Übergänge** (`RA-06`). Jedes gespeicherte Objekt führt die
Fassung der Norm, des Vokabulars und des Rasters mit, unter denen es entstanden ist.
Ändert sich die Bedeutung eines Werts, wird der Übergang festgehalten (`NR-09`).

**Herkunft an jedem Ergebnis** (`RA-10`, `NR-07`). Herkunft ist ein Feld, kein
Satzbaustein. Zu jedem Wert muss abrufbar sein, woher er stammt.

**Unsicherheit ist ein Feld** (`RA-11`). Nicht «vermutlich» im Fliesstext, sondern
ein Wert aus einer geschlossenen Liste. Was nur sprachlich unsicher ist, lässt sich
nicht auswerten und verschwindet beim ersten Umformulieren.

**Kontrolliertes Vokabular** (`RA-12`, `NR-06`). Klassifiziert wird nur in
bestehende Listen. Ein neuer Wert braucht eine Freigabe — er entsteht nicht durch
Eintippen. Zu jeder Liste ist festgelegt, was mit einem Wert ausserhalb geschieht.

**Zwei verbindliche Muster** aus der Referenzarchitektur:

1. **Das verfolgte Ding und seine Belege werden getrennt.** Ein Eintrag hat eine
   eigene Identität; datierte Beobachtungen docken daran an. Nur so lässt sich
   Bewegung über die Zeit zeigen.
2. **Die Bewertung ist ein eigenes, versioniertes Objekt mit Zeitstempel** — nicht
   ein Feld am bewerteten Ding. Der Verlauf entsteht dadurch kostenlos.

**Nachweise sind unveränderlich** (`RA-13`, `NR-10`). Ein ausgestellter Nachweis
wird nicht nachbearbeitet. Korrekturen entstehen als neuer Nachweis mit Bezug auf
den alten.

---

## Mandantentrennung

Gilt, sobald mehr als eine Organisation mit dem Werkzeug arbeitet — auch wenn
heute erst eine da ist.

**Trennung ist Struktur, nicht Filter** (`RA-08`). Ein vergessenes `WHERE` ist ein
Datenschutzvorfall; eine fehlende Struktur ist ein Fehler beim Bauen. Der
Unterschied ist, dass der zweite auffällt und der erste nicht.

**Keine Mandantengrenze überschreiten — lesend, schreibend oder als Vorlage**
(`NR-04`). Der dritte Fall ist der übersehene: Die Vorlage einer Organisation darf
nicht der Voreinstellung einer anderen dienen, auch nicht «nur zur Anregung».

**Geteilte Referenzbestände sind ausdrücklich geteilt.** Ein Bestand ohne
Mandantenzuordnung ist geteilt, weil jemand das entschieden hat — nicht, weil das
Feld leer geblieben ist. Der Unterschied gehört ins Datenmodell, nicht in eine
Konvention.

**Drei Konfigurationsebenen, sauber getrennt:** Basis (gilt für alle) · Mandant
(Zusätze und Abweichungen) · Instanz oder Projekt. Was auf einer unteren Ebene
gesetzt wird, überschreibt nie eine Zusicherung der oberen, sondern nur deren
Voreinstellungen.

**Prüfbar:** Zu jedem Zugriff lässt sich zeigen, welcher Mandant ihn ausgelöst hat
und welche Struktur ihn begrenzt hat. Ein Test, der nur den erlaubten Fall prüft,
prüft nichts — es braucht den Fall über die Grenze hinweg, und er muss fehlschlagen.

---

## Oberfläche

Gilt für jedes Werkzeug mit einer Bedienoberfläche.

> **Unvollständig.** Die Bedienungsnorm (UX-Leitfaden, familienweit) und der
> Styleguide liegen nicht in dieser Ablage. Was hier steht, sind die Anforderungen,
> die Referenzarchitektur und Rahmenwerk an die Oberfläche stellen — nicht die
> acht Prinzipien selbst. Sobald die Bedienungsnorm hier liegt und ihre Kennungen
> hat, ersetzt sie diesen Abschnitt.

**Die Oberfläche ist eine Norm, keine Geschmacksfrage.** Sie steht auf derselben
Ebene wie die Referenzarchitektur und ist aus der Haltung abgeleitet, nicht aus
Stilempfinden. Das Produkt **ergänzt** die familienweiten Prinzipien; es weicht
nicht ab.

**Was das Datenmodell tragen muss**, damit die Oberfläche es überhaupt einlösen
kann — deshalb steht es hier und nicht in der Zuständigkeit der Oberfläche:

| Anforderung | Was dafür geführt wird |
|---|---|
| Der Mensch entscheidet, das System schlägt vor | Entwurfs- und Bestätigungsfeld getrennt (`RA-04`); ein Zustand, der Entwurf von Verbindlichem unterscheidet |
| Keine Aussage ohne Quelle | Herkunft je Wert abrufbar (`RA-10`); Quellenangabe als **Pflichtfeld**, nicht als Textkonvention |
| Sicherheitsgrad sichtbar | Unsicherheit als Feld aus geschlossener Liste (`RA-11`) |

**Vier Regeln, die maschinell prüfbar sind** und deshalb nicht von der Sorgfalt der
Entwicklung abhängen sollen:

- Ein **Entwurf ist als Entwurf ausgezeichnet** und wird erst durch eine benannte
  Handlung verbindlich.
- **Farbe ist nie das einzige Signal.**
- **Klickziele haben eine Mindestgrösse.**
- **Kein Wert wird ohne Herkunft angezeigt.**

Diese vier gehören in die Regelprüfung, nicht in ein Review. Solange das nicht
gebaut ist, sind sie beim Bauen von Hand einzuhalten — und ihr Fehlen ist ein Befund,
kein Versehen.

**Ein gesperrter Knopf ohne Auskunft ist keiner.** Wo eine Handlung nicht möglich
ist, steht der Grund daneben.

---

## Tests und Nachweis

**Das Protokoll ist der Nachweis** (`RA-13`). Ein Lauf, der kein versioniertes
Protokoll hinterlässt, hat nicht stattgefunden — er ist nur gut ausgegangen.

**«Keine Tests» heisst «nicht geprüft», nicht «bestanden».** Und es wiegt genauso
schwer wie ein roter Lauf. Wer das anders zählt, belohnt das Weglassen.

**Prüfer ≠ Erzeuger.** Ein Agent darf nicht zugleich das erwartete Ergebnis
erfinden und über dessen Erfüllung urteilen. Dieselbe Trennung gilt für Menschen:
Wer die Spezifikation geschrieben hat, nimmt sie nicht ab.

**Die Trennung steht im Code, nicht in einer Anweisung** (`NR-08`). Wo ein Prüfer
etwas nicht sehen soll, wird ihm die Eingabemenge im Code zusammengestellt — er
prüft den Text, nicht die vermutete Absicht.

**Ein Regressionstest sagt, was er beweist.** Die erste Zeile beginnt mit
`"""Beweist: …"""`. Ein Test ohne diesen Satz prüft irgendetwas, und beim nächsten
Umbau wird er angepasst, bis er wieder grün ist.

**Zahlen zählt der Code.** Zählungen, Gewichte und Befundsummen werden gerechnet,
nicht vom Modell übernommen. Ein unbekanntes Befundgewicht zählt als **Muss** statt
aus der Zählung zu fallen.

**Ein Muss-Befund hält an.** Offene Muss-Befunde einer Stufe verhindern die nächste.
Der Grund steht am abgeblendeten Knopf.

**Eine Freigabeversion ist nie befundfrei.** Mehr Präzision erzeugt mehr prüfbare
Behauptungen und damit mehr Befunde; eine Prüfschleife konvergiert auf einem dichten
Gegenstand nicht von selbst. Wer keine Restbefunde sieht, hat nicht gut gearbeitet,
sondern zu wenig geprüft.

**Deterministisch vor urteilend.** Was ohne Urteil entscheidbar ist, gehört in den
Kern — dort ist es reproduzierbar und nicht vom Modell steuerbar. Faustregel:
deterministisch prüfbare Kriterien in den Kern, fachlich zu beurteilende in die
Methode.

---

## Betrieb und Umgebungen

**Vier Umgebungen, sequenzielle Promotion:** `develop → test → integration → main`.
Es wird **keine Stufe übersprungen**, auch nicht für eine kleine Änderung.

> **`test` ist die Kundenumgebung.** Dorthin wird nur auf ausdrückliche Anweisung
> promoviert. Wer sie wie eine Entwicklungsstufe behandelt, zeigt dem Kunden einen
> Zwischenstand, den niemand freigegeben hat.

**Version je Promotion.** Jede Promotion erhöht die Version. Eine Fassung ohne
eigene Nummer lässt sich später keinem Nachweis zuordnen.

**Portblock je Produkt.** Jedes Produkt hat einen festen, zusammenhängenden Block —
eine Umgebung, ein Port. Der Block steht im README des Repositories; Ports werden
nicht geraten und nicht wiederverwendet.

**Schlüssel gehören in die `.env` und nirgendwo sonst.** Die Datei ist ignoriert,
die Anwendung liest sie beim Start und **schreibt keinen Schlüssel ins Protokoll**.
Ein Schlüssel im Repository ist ein Vorfall, kein Versehen — auch in der Historie.

**Was beim Start unklar ist, meldet sich beim Start.** Fehlender Vorschaltdienst,
Direktmodus, Prüfer auf demselben Modell, fehlende Norm: eine Warnung im Protokoll,
nicht ein stilles Weiterlaufen. Ein Zustand, den niemand sieht, wird zum
Normalzustand.

**Die Norm wird gelesen, nicht abgeschrieben.** Wo eine Anwendung gegen eine Norm
prüft, lädt sie deren jüngste Fassung aus dem Normverzeichnis und weist zurück, was
die erwarteten Kennungen nicht enthält. Eine Abschrift im Code veraltet still.

**Lokale Artefakte gehören nicht ins Repository:** Datenbanken, `.env` ausser dem
Beispiel, virtuelle Umgebungen, Zwischenstände, Laufzeit-Caches. Was einmal
eingecheckt wurde, wird aus dem Index entfernt, ohne die lokale Datei zu löschen.

---

## Nur in diesem Repository

**Die vier Grundprinzipien gehen allem vor:** Rechtssicherheit,
Nachvollziehbarkeit, Datenschutz und Informationssicherheit, Datenqualität. Sie
stehen im Grundsatzdokument des Repositories und gelten auch für das BPMN-Werkzeug.

**Eine Simulation ist ein Vorschlag, kein Befund.** Rechenergebnisse werden mit
ihren Annahmen ausgegeben; eine Kennzahl ohne ihre Annahme ist eine Behauptung
(`RA-10`, `RA-11`).

**Das Versprechen im README ist unbedingt formuliert.** «Löst genau das» trägt
keinen Vorbehalt — beim nächsten Überarbeiten anpassen, sonst behauptet die
Beschreibung mehr, als die Rechnung hergibt.

**Die Erweiterungsattribute im Prozessmodell sind Vokabular**, kein freies Feld
(`RA-12`, `NR-06`).
