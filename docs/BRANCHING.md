# Branch-Strategie

```
OpenLegalLab2026   (eingefroren: Original-Stand Hackathon, nur Referenz)

dev  ──►  test  ──►  integration  ──►  main
(Entw.)   (Test)     (Integration)     (Produktion)
```

| Branch            | Zweck                              | Deploy            |
|-------------------|------------------------------------|-------------------|
| `OpenLegalLab2026`| Original aus dem Hackathon, **eingefroren** | – |
| `dev`             | laufende Entwicklung               | nur CI-Tests      |
| `test`            | Testumgebung                       | test.ditwi.ch :8011 |
| `integration`     | Integrationsumgebung               | int.ditwi.ch :8012  |
| `main`            | Produktion                         | ditwi.ch :8010      |

## Regeln

- **Promotion immer sequenziell:** `dev → test → integration → main`.
  Nie eine Stufe überspringen – auch nicht für einen Prod-Hotfix.
- Promotion per Pull Request (Merge der jeweils vorgelagerten Stufe).
- `OpenLegalLab2026` wird **nicht** verändert.

## Empfohlener Branch-Schutz (GitHub)

Für `main` (und sinnvollerweise `integration`):
- PR erforderlich, keine direkten Pushes
- Status-Check „Tests" muss grün sein
- lineare History

## Typischer Ablauf

```bash
# Feature auf dev entwickeln
git switch dev && git pull
# ... committen ...
git push

# nach grünem dev-Build hochpromoten:
#   PR dev → test, dann test → integration, dann integration → main
# Jeder Merge triggert den jeweiligen Jenkins-Job (Tests + Deploy).
```
