Prozess-Simulator (ProS)

Simuliere Prozesse. Verstehe Engpässe. Triff bessere Entscheidungen.


Überblick

Der Prozess-Simulator (ProS) ist eine webbasierte Anwendung zur:

Modellierung von Geschäftsprozessen (BPMN-ähnlich)
Abbildung von Organisationen
Simulation von Kapazität, Auslastung und Kosten
Identifikation von Engpässen (strategisch & operativ)

Entwickelt im Rahmen des Open Legal Lab 2026

Warum dieses Tool?

Organisationen wissen oft:

nicht, wo ihre Engpässe sind
nicht, ob Zielvorgaben realistisch sind
nicht, wie sich Änderungen auswirken

ProS löst genau das.

Kernidee
Prozess  ×  Organisation  ×  Ressourcen

Diese drei Dimensionen werden verknüpft und rechnerisch ausgewertet.

Features
Prozessmodellierung
Drag & Drop BPMN-ähnlicher Editor
Tasks (Aktivitäten)
XOR-Entscheidungen mit Prozenten
Subprozesse (klickbar & verschachtelt)
Prozesslandkarte (End-to-End Sicht)

Organisationsmodell
Mehrere Organisationen
Hierarchien (Departement → Stellen)
Personen mit:
FTE (Beschäftigungsgrad)
Rollen & Funktionen
Gehalt

Intelligente Zuweisungen
Stellen → Aktivitäten
Funktionen → Aktivitäten
Rollen/Funktionen → Personen

Validierung:

falsche Zuweisungen werden visuell hervorgehoben
Dashboard
Strategisch

Engpassanalyse
Farblogik:
🔴 Engpass
🟡 kritisch
🟢 stabil
⚙️ Operativ

Fälle pro:
Tag / Woche / Monat / Jahr
Anzeige:
Kapazität vs. Bedarf
fehlende Stunden / Fälle
visuelle Überlastung
Screenshots (optional einfügen)
![Dashboard](docs/screenshots/dashboard.png)
![Process](docs/screenshots/process.png)

Architektur
Browser
   ↓
Flask (app.py)
   ↓
Business Logic (dashboard.py)
   ↓
SQLAlchemy (models.py)
   ↓
PostgreSQL / SQLite

Technologie-Stack
Bereich	Technologie
Backend	Flask
ORM	SQLAlchemy
Datenbank	PostgreSQL / SQLite
Frontend	HTML, CSS, JS
Packaging	PyInstaller (.exe)

Projektstruktur
legal_lab_strafbefehl_mvp/
│
├── app/
│   ├── app.py
│   ├── models.py
│   ├── dashboard.py
│   ├── templates/
│   └── static/
│
├── run.py
├── requirements.txt
└── .venv/

Setup (Development)
1. Clone
git clone <repo-url>
cd legal_lab_strafbefehl_mvp
2. Virtual Environment
python -m venv .venv
3. Aktivieren

Windows

.venv\Scripts\activate

Mac/Linux

source .venv/bin/activate

4. Dependencies
pip install -r requirements.txt
5. Environment

.env erstellen:

DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/prozess_simulator
FLASK_SECRET_KEY=super-secret-key
6. Start
python run.py

Öffnen:

http://127.0.0.1:5000
Desktop-Version (.exe)

Für Nicht-Techniker:

✔ kein Python nötig
✔ keine Datenbankinstallation

Build
build_exe.bat
Output
dist/Prozess-Simulator/

gesamten Ordner weitergeben

Fachliche Grundlagen

Der Simulator basiert auf:

Kapazität = Arbeitszeit / Aufwand
Engpass bestimmt Gesamtleistung
Parallelität erhöht Durchsatz
XOR verteilt Fälle probabilistisch

Annahmen
konstante Bearbeitungszeiten
keine Warteschlangen
keine Priorisierung
keine Störungen
nur XOR (kein AND-Gateway)

Roadmap
AND-Gateways
echte Simulation (Queueing)
Multi-User / Rechte
zentrale Server-Version
Versionierung

Team
M. Balmer
K. Brönnimann
N. Gloor
D. Kettiger
X. Schütz
T. Hügli

Kontext

Open Legal Lab 2026
Magglingen
25.–27. April 2026

Lizenz

Empfohlen:

MIT License

Beitrag

Pull Requests sind willkommen!

Kontakt

Bei Fragen oder Interesse einfach melden 🙂

Wenn Dir das Tool gefällt

Gib dem Repo ein ⭐ – hilft enorm!

