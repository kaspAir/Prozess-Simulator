# Server-Setup (Infomaniak Managed Hosting)

Einmalige Vorbereitung auf dem Server, damit die Jenkins-Pipeline deployen kann.
Deploy erfolgt **ohne Docker** (Managed Hosting), als Gunicorn-Prozesse hinter dem
Reverse-Proxy/HTTPS des Hosting-Panels.

## Umgebungen / Ports / Domains

| Branch       | App-Verzeichnis              | Port  | Domain          |
|--------------|------------------------------|-------|-----------------|
| `main`       | `~/prozess-simulator`        | 8010  | ditwi.ch        |
| `integration`| `~/prozess-simulator-int`    | 8012  | int.ditwi.ch    |
| `test`       | `~/prozess-simulator-test`   | 8011  | test.ditwi.ch   |
| `dev`        | — (nur Tests in CI)          | —     | —               |

> Die hermespia.ch-Instanz nutzt 8000/8001/8002 — ProS nutzt 8010/8011/8012,
> damit sich beide Anwendungen auf demselben Host nicht stören.

## Einmalige Schritte pro Umgebung

Die Pipeline initialisiert das Repo direkt im App-Verzeichnis (`git init` +
`fetch` + `reset --hard`) und legt das venv automatisch an. Vorher müssen nur
das Verzeichnis und die `.env` existieren – `.env`, `data/` und `logs/` bleiben
als nicht versionierte Dateien beim Deploy erhalten. Beispiel für **prod**:

> **venv auf Managed Hosting:** `python3 -m venv` funktioniert dort nicht
> (kein `ensurepip`/`python3-venv`, kein root). Die Pipeline erstellt das venv
> daher mit **`virtualenv`** (`python3 -m pip install --user virtualenv` →
> `python3 -m virtualenv .venv`). Innerhalb des aktivierten venv existiert dann
> auch `python` (auf dem Host selbst gibt es nur `python3`).

```bash
APP_DIR=$HOME/prozess-simulator        # bzw. -test / -int
mkdir -p "$APP_DIR/data" "$APP_DIR/logs" "$HOME/tmp"

# Hinweis: $APP_DIR muss hier expandieren -> KEINE Quotes um EOF.
cat > "$APP_DIR/.env" <<EOF
FLASK_SECRET_KEY=<langer-zufaelliger-wert>
DATABASE_URL=sqlite:///$APP_DIR/data/prozess_simulator.db
FLASK_DEBUG=0
# Bootstrap-Admin (erster Super-/Account-Admin), vom Auth-Seed angelegt:
BOOTSTRAP_ACCOUNT_NAME=ditwi
BOOTSTRAP_ADMIN_NAME=Kaspar Broennimann
BOOTSTRAP_ADMIN_EMAIL=<deine-email>
BOOTSTRAP_ADMIN_PASSWORD=<starkes-passwort>
EOF
```

> Der Deploy ruft nach `init_db.py` ein **idempotentes** `seed_auth.py`, das Account,
> Vorlagen-Rollen und – bei gesetzten `BOOTSTRAP_ADMIN_*` – den ersten Admin anlegt.
> Nach dem ersten Login kann das Passwort in der App geändert werden.

Für `-test` und `-int` analog (eigener `FLASK_SECRET_KEY`, eigenes `data/`).

> **Wichtig – absoluter DB-Pfad:** Flask-SQLAlchemy löst *relative* SQLite-Pfade
> gegen den `instance/`-Ordner auf, der Deploy-Check (`[ -f data/... ]`) aber gegen
> das App-Verzeichnis. Ein relativer Pfad würde beide auseinanderlaufen lassen –
> `init_db.py` (mit `drop_all`) liefe dann bei jedem Deploy und löschte die Daten.
> Deshalb den **absoluten** Pfad `sqlite:///$APP_DIR/data/...` verwenden.
> Beim ersten Deploy wird die DB via `python init_db.py` mit Demo-Daten angelegt.

## Jenkins-Jobs

Pro Branch ein Pipeline-Job, dessen **Name den Branch enthält** (die Pipeline
schaltet die Deploy-Stage über `JOB_NAME.contains('<branch>')`):

- `prozess-simulator-dev`         → Branch `dev`         (nur Tests)
- `prozess-simulator-test`        → Branch `test`        (Tests + Deploy 8011)
- `prozess-simulator-integration` → Branch `integration` (Tests + Deploy 8012)
- `prozess-simulator-main`        → Branch `main`        (Tests + Deploy 8010)

Jeder Job: *Pipeline script from SCM*, Repo `https://github.com/kaspAir/Prozess-Simulator`,
passender Branch, Script Path `Jenkinsfile`. Benötigt das Credential
`hermespia-deploy` (SSH) und Docker auf dem Jenkins-Agent.

## HTTPS / Reverse-Proxy

Auf Managed Hosting kein nginx/Root. Reverse-Proxy auf den lokalen Gunicorn-Port
und TLS laufen über das Infomaniak-Panel (Let's Encrypt) bzw. den dort genutzten
Proxy-Mechanismus (analog hermespia.ch). DNS: A-Records für `ditwi.ch`,
`test.ditwi.ch`, `int.ditwi.ch` auf den Host zeigen lassen.

Für einen späteren Umzug auf einen Root-/VPS-Server liegt eine nginx-Vorlage unter
`deploy/nginx-prozess-simulator.conf` bereit.
