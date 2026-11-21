# CLAUDE.md

## Projektziel
wger (Django, Python >= 3.12) soll als reguläre Cloud-Foundry-App mit Buildpacks laufen (kein Docker-Image). Upstream: https://github.com/wger-project/wger

## Regeln
- Arbeitsbranch: `cf-port`. Nicht direkt auf `master` committen.
- Upstream-Code möglichst nicht ändern. CF-spezifische Dateien in `cf/` oder als separates Settings-Overlay ablegen, damit Upstream-Merges einfach bleiben.
- Die Projekt-README liegt unter `cf/README.md`. Die `README.md` im Wurzelverzeichnis gehört Upstream und bleibt unverändert, sonst kollidiert jeder Upstream-Merge an dieser Datei.
- Keine Zugangsdaten, internen Vorgangsnummern, konkreten Einsatzorte/-zeiten oder klassifizierten Informationen ins Repo, in Commits oder Prompts. Beispiele anonymisieren.
- Nichts raten: Wenn etwas unklar oder nicht verifiziert ist, im Code/der Doku als "bitte prüfen" markieren oder nachfragen.
- Lizenz AGPL-3.0-or-later beachten.

## Verfügbare CF-Services
- PostgreSQL
- Redis
- S3 (S3-kompatibel)
- Mail/SMTP: ungeklärt

Zugangsdaten kommen ausschließlich über Service-Bindings (`VCAP_SERVICES`), nie hartcodiert.

## Aufgaben (Reihenfolge)
1. `settings/` und Umgebungsvariablen analysieren, Liste der benötigten Variablen erstellen.
2. `uv export` nach `requirements.txt` (alternativ Buildpack-Unterstützung für uv prüfen). Python-/Node-Version gegen `cf buildpacks` abgleichen.
3. Settings-Overlay: `VCAP_SERVICES` auf Datenbank, Redis (Celery-Broker, Cache) und S3 (`django-storages`, `boto3`) abbilden.
4. Static-Files-Auslieferung klären (z. B. `whitenoise` ergänzen oder S3). Frontend-Assets (`package.json`) in der CI vorbauen oder per Multi-Buildpack (`nodejs_buildpack` + `python_buildpack`).
5. `manifest.yml`: `wger-web` (gunicorn), `wger-worker` (Celery), optional `wger-beat`. Healthcheck und Service-Bindings setzen.
6. Migrationen und Initialdaten per `cf run-task`, nicht beim App-Start.
7. Ersten Test-Push zuerst ohne Worker, dann Worker und Storage ergänzen.
8. Betrieb in der README dokumentieren.

## Hinweise
- Das CF-Dateisystem ist flüchtig: keine lokalen Uploads.
- Stemcells sind BOSH-Plattformebene, für die App nicht relevant. Die App läuft auf dem Root-Filesystem der Plattform (z. B. `cflinuxfs4`).
- Die Annahmen in diesem Dokument stammen aus den Abhängigkeiten (`pyproject.toml`), die Settings wurden noch nicht gelesen.
