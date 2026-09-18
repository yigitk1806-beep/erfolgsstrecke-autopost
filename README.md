# erfolgsstrecke autopost

Veröffentlicht freigegebene Instagram-Beiträge automatisch — kostenlos über Instagrams offizielle Schnittstelle und GitHub Actions.

## So funktioniert es

- Jeder Beitrag ist ein Ordner in `queue/` mit einer `post.json` und den Bildern bzw. dem Video.
- Alle 15 Minuten prüft GitHub, ob ein Beitrag fällig ist.
- Veröffentlicht wird **nur**, wenn `"approved": true` gesetzt und `publish_at` erreicht ist.
- Danach wandert der Ordner nach `published/`, mit der Instagram-ID des Beitrags.
- Nach 3 Fehlversuchen wird ein Beitrag nicht weiter versucht, bis jemand ihn prüft.

## Beitrag anlegen

```
queue/
  2026-09-22-1800-denkfehler/
    post.json
    1.jpg
    2.jpg
```

Felder der `post.json` (Vorlage: `beispiel-post.json`):

| Feld | Bedeutung |
|---|---|
| `publish_at` | Zeitpunkt mit Zeitzone, z. B. `2026-09-22T18:00:00+02:00` |
| `type` | `image`, `carousel` oder `reel` |
| `caption` | Bildunterschrift inkl. Hashtags |
| `media` | Dateinamen in Reihenfolge |
| `approved` | erst nach Freigabe auf `true` |

Regeln: Bilder nur **JPEG**, Karussell 2–10 Bilder, Ordner- und Dateinamen ohne Leerzeichen.

## Einmalige Einrichtung

1. Meta-App mit *Instagram API with Instagram Login* anlegen, eigenes Konto als Instagram-Tester eintragen, Zugangsschlüssel erzeugen.
2. Dieses Repository **öffentlich** auf GitHub anlegen — Instagram muss die Bilder abrufen können.
3. Unter *Settings → Secrets and variables → Actions* anlegen:
   - `IG_USER_ID` — Instagram-Konto-ID
   - `IG_ACCESS_TOKEN` — Zugangsschlüssel (gilt 60 Tage, wird wöchentlich erneuert)
   - `GH_PAT` — optional, damit ein erneuerter Schlüssel automatisch gespeichert wird
4. *Actions → Verbindung testen → Run workflow* — prüft die Verbindung, postet nichts.
5. *Actions → Instagram veroeffentlichen → Run workflow* — startet von Hand standardmäßig als Probelauf.

## Reels

GitHub liefert Videos über `raw.githubusercontent.com` unter Umständen nicht im erwarteten Format. Falls Reels scheitern: GitHub Pages aktivieren und die Variable `MEDIA_BASE_URL` auf `https://<benutzer>.github.io/<repository>` setzen.

## Hinweise

- GitHub pausiert Zeitpläne in Repositories, die 60 Tage lang keine Änderungen hatten. Jede Veröffentlichung erzeugt eine Änderung — bei regelmäßigem Posten passiert das also nicht.
- Schlüssel und Passwörter gehören ausschließlich in GitHub Secrets, nie in Dateien.
