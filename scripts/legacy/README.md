# Legacy-Skripte (Archiv)

Diese Skripte stammen aus der Hackathon-Phase (Open Legal Lab 2026). Es handelt
sich um **einmalige, bereits angewandte** Datenbank-Migrationen und Hilfsskripte.

Sie sind **nicht Teil des laufenden Betriebs** und werden vom App-Code nicht
importiert. Sie sind nur zur Nachvollziehbarkeit der Datenmodell-Entwicklung
aufbewahrt.

Hinweis: Die Skripte importierten urspruenglich `from app.app import app, db`.
Dieses Modul wurde im Zuge der Bereinigung entfernt (kanonische Factory ist jetzt
`app/__init__.py::create_app()`). Wer eines der Skripte erneut ausfuehren will,
muss den Import auf folgendes Muster umstellen:

```python
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    ...
```

Für eine **frische** Datenbank wird ohnehin nur `python init_db.py` benoetigt.
