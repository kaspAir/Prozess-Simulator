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
Flask (run.py → app/__init__.py: create_app)
   ↓
Blueprints (app/routes/) + Services (app/services/)
   ↓
Business Logic (app/dashboard.py, app/calculations.py)
   ↓
SQLAlchemy (app/models.py)
   ↓
SQLite (Standard) / PostgreSQL (optional)

Technologie-Stack
Bereich	Technologie
Backend	Flask
ORM	SQLAlchemy
Datenbank	PostgreSQL / SQLite
Frontend	HTML, CSS, JS
Container	Docker / docker-compose
CI/CD	Jenkins

Projektstruktur
Prozess-Simulator/
│
├── app/
│   ├── __init__.py          # create_app() – kanonische App-Factory
│   ├── models.py            # SQLAlchemy-Modelle
│   ├── dashboard.py         # Kennzahlen/Engpass-Logik
│   ├── calculations.py
│   ├── simulation.py
│   ├── routes/              # Blueprints: main, organization, process
│   ├── services/            # Service-Schicht (Datenzugriff)
│   ├── templates/
│   └── static/
│
├── tests/                   # Smoke-Tests (pytest)
├── deploy/                  # Server-/Deploy-Konfiguration
├── scripts/legacy/          # archivierte Hackathon-Migrationen
├── docs/legacy/             # archivierte Hackathon-Doku
├── run.py                   # Einstiegspunkt (Gunicorn: run:app)
├── init_db.py               # DB anlegen + Demo-Daten seeden
├── Dockerfile
├── docker-compose.yml
├── Jenkinsfile
└── requirements.txt

## Setup & Betrieb

### Variante A — Lokal mit Docker (empfohlen für schnellen Start)

```bash
docker compose up --build
```

Beim ersten Start wird automatisch eine SQLite-Datenbank angelegt und mit
Demo-Daten befüllt. App öffnen: <http://localhost:5000>

PostgreSQL statt SQLite testen:

```bash
# DATABASE_URL in einer .env setzen (siehe .env.example), dann:
docker compose --profile pg up --build
```

### Variante B — Ohne Docker (venv)

```bash
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS/Linux:    source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # Standard ist SQLite – läuft ohne DB-Server
python init_db.py           # DB anlegen + Demo-Daten
python run.py               # http://127.0.0.1:5000
```

### Tests

```bash
pip install -r tests/requirements.txt
pytest tests/ -v
```

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

