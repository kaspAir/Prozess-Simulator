# ditwi.ch öffentlich erreichbar machen (HTTPS)

Die App läuft bereits als Gunicorn auf `127.0.0.1:8010` (prod), `:8011` (test),
`:8012` (int). Es fehlt nur der **öffentliche Eingang**: Domain → Web-Root →
PHP-Reverse-Proxy → lokaler Port, plus TLS.

## Brauche ich ein neues Hosting?

**Nein, sehr wahrscheinlich nicht.** Die Deploys laufen bereits auf deinem
bestehenden Infomaniak Web Hosting (`/home/clients/…`, derselbe Account wie
hermespia.ch). Infomaniak Web Hosting erlaubt **mehrere Websites pro Abo**
(dein Tarif: bis 20). ditwi.ch wird einfach als **zusätzliche Site** ergänzt –
kein zweites Abo, kein Aufpreis, solange ein Website-Slot frei ist.

Ein neues Hosting nur dann, wenn (a) alle Slots belegt sind oder (b) du strikte
Trennung willst.

## Schritte

### 1. Domain als Site im bestehenden Hosting hinzufügen (Infomaniak-Panel)
- Hosting öffnen → **Websites verwalten** → **Website hinzufügen** → `ditwi.ch`.
- Als **Dokument-Root** einen eigenen Ordner wählen, z. B. `sites/ditwi.ch`.
- Für Subdomains `test.ditwi.ch` / `int.ditwi.ch` analog je eigenen Web-Root.

### 2. PHP-Reverse-Proxy in den Web-Root legen
Aus `deploy/php-proxy/` in den Web-Root der Site kopieren (SFTP/SSH/Dateimanager):
- `index.php`  (Port im Skript prüfen: ditwi.ch = **8010**)
- `.htaccess`

Beispiel per SSH:
```bash
SITE=$HOME/sites/ditwi.ch          # an deinen Dokument-Root anpassen
mkdir -p "$SITE"
cp $HOME/prozess-simulator/deploy/php-proxy/index.php   "$SITE/"
cp $HOME/prozess-simulator/deploy/php-proxy/.htaccess   "$SITE/"
# Für test/int: index.php kopieren und $TARGET_PORT auf 8011 bzw. 8012 setzen.
```

### 3. HTTPS aktivieren (Infomaniak-Panel)
- Bei der Site **SSL/TLS-Zertifikat (Let's Encrypt)** für `ditwi.ch`
  (und ggf. `www.`, `test.`, `int.`) ausstellen lassen.
- **HTTPS erzwingen** (HTTP → HTTPS Redirect) aktivieren.

### 4. DNS prüfen
`ditwi.ch` (und Subdomains) müssen auf den Hosting-Host zeigen. Liegt die Domain
bei Infomaniak, ist das meist automatisch gesetzt.

### Test
```bash
curl -I https://ditwi.ch        # 200/302 vom Prozess-Simulator
```

## Hinweis: an hermespia.ch ausrichten
Falls hermespia.ch einen leicht anderen Proxy verwendet (eigene `index.php`/
`.htaccess`), diese als Vorlage nehmen und nur Ziel-Port (8010/8011/8012) +
Domain anpassen – dann ist das Verhalten identisch zur bewährten Instanz.
