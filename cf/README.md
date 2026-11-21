# cf-wger

Portierung von [wger](https://github.com/wger-project/wger) (Workout-, Ernährungs- und Gewichts-Tracker, Django/Python) auf **Cloud Foundry**. Die Anwendung soll mit den **Buildpacks** der Plattform gebaut und betrieben werden, statt als Docker-Container.

> Status: Planung / Initialisierung. Alle Angaben unten sind Arbeitsannahmen und müssen im Projekt geprüft werden.

## Hintergrund

wger wird upstream vor allem per Docker Compose betrieben. Wir wollen prüfen und umsetzen, ob die Anwendung auf unserer Cloud-Foundry-Plattform als reguläre CF-App laufen kann:

- Build und Laufzeit über **Buildpacks** (kein eigenes Image)
- Betrieb auf dem Root-Filesystem der Plattform (z. B. `cflinuxfs4`). Stemcells sind BOSH-VM-Images der Plattformebene und werden vom Plattformbetreiber gepflegt, die App nutzt sie nicht direkt.
- Anbindung an Marketplace-Services statt lokaler Container

Das Repo ist ein Fork/Abzweig von `wger-project/wger`. Ziel ist, Upstream-Code möglichst wenig zu ändern, damit sich Updates weiter einspielen lassen.

## Ziele

1. Lauffähige wger-Instanz in einem CF-Test-Space
2. Reproduzierbarer Deploy per `cf push` mit `manifest.yml`
3. Konfiguration ausschließlich über Umgebungsvariablen und Service-Bindings (`VCAP_SERVICES`)
4. Dokumentierter Betrieb (Migrationen, Worker, Betrieb, Updates)

## Nicht-Ziele

- Änderungen an der Fachlogik von wger
- Produktivbetrieb vor erfolgreichem Test (Sicherheit, Datenschutz, Betrieb sind separat zu klären)

## Geplante Architektur

| Komponente | Zweck | Umsetzung auf CF |
|---|---|---|
| `wger-web` | Django-Anwendung | App mit gunicorn |
| `wger-worker` | Hintergrundjobs (Celery) | eigene App oder zusätzlicher Prozesstyp |
| `wger-beat` | geplante Tasks (optional) | eigene App, nur falls benötigt |
| Flower | Celery-Monitoring (optional) | nur zum Debuggen |

## Benötigte Services

Aus den Abhängigkeiten abgeleitet, noch nicht gegen die Settings geprüft:

| Service | Verwendung | Status |
|---|---|---|
| PostgreSQL | Hauptdatenbank | Pflicht |
| Redis | Celery-Broker, Cache | Pflicht |
| S3-kompatibler Object Storage | Uploads, z. B. Fortschrittsfotos (CF-Dateisystem ist flüchtig) | Pflicht |
| SMTP/Mail | Registrierung, Passwort-Reset | optional |
| Monitoring/Logging | Prometheus-Endpoint ist vorhanden | optional |

**Verfügbare Services in unserer Umgebung (CF Marketplace):** PostgreSQL, Redis, S3.
Mail/SMTP: _noch zu klären_. Konkrete Service-Pläne, Namen und Versionen: _noch zu ergänzen_.

## Bekannte Aufgaben / Anpassungen

- [ ] Abhängigkeiten: `uv.lock` nach `requirements.txt` exportieren (oder Buildpack-Unterstützung für uv prüfen)
- [ ] Python- und Node-Versionen gegen die installierten Buildpacks prüfen (`cf buildpacks`)
- [ ] Frontend-Assets: in der CI vorbauen oder Multi-Buildpack (`nodejs_buildpack` + `python_buildpack`)
- [ ] Settings-Overlay: `VCAP_SERVICES` auf `DATABASE_URL`, Redis-URL und Storage-Konfiguration abbilden
- [ ] Static-Files: Auslieferung klären (z. B. `whitenoise` oder Object Storage)
- [ ] Media-Uploads auf S3 umstellen (`django-storages`)
- [ ] `manifest.yml` mit Prozesstypen und Service-Bindings
- [ ] Migrationen und Initialdaten per `cf run-task` ausführen
- [ ] Healthcheck konfigurieren
- [ ] Betrieb dokumentieren

## Vorgehen

1. Settings und Umgebungsvariablen von wger analysieren
2. Minimalen Test-Push ohne Worker durchführen
3. Services binden, Migrationen ausführen
4. Worker und Storage ergänzen
5. Test, Doku, ggf. Übergabe an den Betrieb

## Repository-Konventionen

- Arbeitsbranch: `cf-port`
- Änderungen an Upstream-Dateien minimal halten, CF-spezifische Dateien möglichst separat ablegen (z. B. `cf/`)
- Remote `upstream` zeigt auf `wger-project/wger`, Updates per Merge
- **Keine** Zugangsdaten, internen Vorgangsnummern, konkreten Einsatzorte/-zeiten oder klassifizierten Informationen ins Repo oder in Prompts. Beispiele und Konfigurationen anonymisieren.

## Lizenz

wger steht unter **AGPL-3.0-or-later**. Eigene Änderungen unterliegen derselben Lizenz. Wird die Anwendung Dritten über ein Netzwerk angeboten, müssen die geänderten Quellen bereitgestellt werden. Vor einem Einsatz über den internen Test hinaus bitte intern klären.

## Links

- Upstream: https://github.com/wger-project/wger
- Dokumentation: https://wger.readthedocs.io
