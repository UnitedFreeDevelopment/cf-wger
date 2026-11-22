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
Zielplattform (Annahme, noch nicht gemessen):
- PostgreSQL
- Redis
- S3 (S3-kompatibel)
- Mail/SMTP: ungeklärt

Was sonst über die Zielplattform bekannt ist, stammt aus Gesprächen, nicht aus Messungen in diesem Repo (Stand 2026-11-22, **bitte prüfen**):
- Beim Staging ist kein PyPI-Index erreichbar; das npm-Gegenstück (Mirror) funktioniert. Ein PyPI-Mirror ist beim Plattformteam beantragt. Bis dahin bliebe nur Vendoring (`pip download --only-binary=:all:` nach `vendor/`, der klassische `python_buildpack` installiert von dort), nicht getestet.
- Der klassische `python_buildpack` meldet dort beim Detect `python: command not found`. Die genannte Version 1.8.122 passt zu keinem Tag des Upstreams `cloudfoundry/python-buildpack` (die 1.8-Reihe endet bei 1.8.43, danach 1.9.x, geprüft 2026-11-22), und `bin/detect` des Upstreams ruft kein `python` auf: es prüft nur, ob `requirements.txt`, `setup.py`, `environment.yml` oder `Pipfile` existiert. Version und Herkunft der Meldung sind offen; erst `cf buildpacks` dort ablesen.
- Anonymer Docker-Pull von Standard-Images ist gesperrt. Das trifft den Lifecycle `cnb` in `cf/manifest.yml`: `docker://docker.io/paketobuildpacks/python` würde dort nicht laden. Ohne Registry-Zugang bleibt der klassische `python_buildpack` mit `runtime.txt`.
- glibc von `cflinuxfs4` ist 2.35 (Ubuntu 22.04; gemessen 2026-11-22 am Image `cloudfoundry/cflinuxfs4`). Wheels bis `manylinux_2_34` laufen damit; die Angabe 2.26 aus einer früheren Problemliste war falsch.

Lokale Entwicklungsplattform `cfk8s-platform` (gemessen am 2026-11-21, `cf marketplace`):
- `cnpg-postgresql` (PostgreSQL, CloudNativePG) – wird genutzt
- `rabbitmq-cluster` – ersetzt Redis als Celery-Broker
- **kein Redis, kein S3.** Cache und Sessions liegen deshalb in der Datenbank, Uploads im flüchtigen Dateisystem. `cf/settings.py` schaltet bei einer Redis- oder S3-Bindung automatisch um; der S3-Zweig ist gegen keine echte Bindung gemessen.
- Gebaut wird mit Cloud Native Buildpacks (`lifecycle: cnb`, `paketobuildpacks/python`). Die Plattform braucht dafür 8 GB Staging-Platte: `make cf-staging-disk` in `cfk8s-platform`. Der klassische `python_buildpack` (`make cf-buildpack-python`) bleibt als Rückfall.
- `collectstatic` läuft lokal in `make -f cf/Makefile assets`, nicht beim Staging; `staticfiles/` wird mitgepusht, `node_modules/` nicht.

Zugangsdaten kommen ausschließlich über Service-Bindings (`VCAP_SERVICES`), nie hartcodiert. Der `SECRET_KEY` liegt im benutzerdefinierten Dienst `wger-secrets`.

## Stand und offene Punkte

Der Stand steht in `cf/README.md` (Dienste, erster Start, Messungen, Betrieb). Was gilt:
- `cf/settings.py` übersetzt `VCAP_SERVICES` in die Variablen von `settings/main.py`; `cf/requirements.lock.txt` kommt aus `uv export`.
- Static-Files liefert whitenoise aus `staticfiles/`, das `make -f cf/Makefile assets` lokal vorbaut; ein `nodejs_buildpack` ist deshalb nicht nötig.
- `cf/manifest.yml` führt `wger-web`, `wger-worker`, `wger-beat` mit Healthcheck und Bindungen; Migrationen laufen als Task (`make -f cf/Makefile init`).

Offen: S3-Zweig ungetestet, E-Mail ungeklärt, Beat nur kurz beobachtet, Heroku-CNB als Größenhebel nicht gemessen, und alles unter „Zielplattform" oben. Einzelheiten in `cf/README.md`, Abschnitt „Offen".

## Ressourcen beim Start (gemessen 2026-11-21, cfk8s-platform)

Die Werte stehen in `cf/manifest.yml` und `cf/Makefile`; hier die Begründung, damit niemand sie „zum Sparen" senkt oder blind erhöht.

| Was | Speicher | Platte | Instanzen | Gemessen |
|---|---|---|---|---|
| `wger-web` | 1G | 2G | 1 (2 geprüft) | 280–320 MB belegt mit zwei Gunicorn-Workern und `--preload`; 1,1 GB Platte vom Droplet. Staging läuft mit dem App-Speicher, unter 1G nicht erprobt |
| `wger-worker` | 512M | 2G | 1 | 190 MB belegt (gevent, Concurrency 2). 2G Platte, weil es dasselbe Droplet ist |
| `wger-beat` | 256M | 2G | **genau 1** | 160 MB belegt. Zwei Beats feuern geplante Aufgaben doppelt |
| `init`-Task | 2G | 2G | – | mit 1G/1G stirbt die Migration `nutrition.0014` mit Exit 137; mehr als 2G Platte lässt die Plattform für Tasks nicht zu |
| Staging (Plattform) | = App-Speicher, min. 1G | **8G** | – | CNB-Export braucht Layer, Cache-Kopie und beide Archive gleichzeitig; bei 4G räumt Kubernetes den Pod (FINDINGS #36 in `cfk8s-platform`). Wird dort gesetzt, nicht im Manifest |

Reihenfolge beim ersten Start: `secrets`, `assets`, `push-web`, `init`, `push` (alles `make -f cf/Makefile …`). Die Apps nacheinander pushen, nicht in einem `cf push -f` für alle drei: parallel laufen sie in den Staging-Timeout von 15 Minuten, einzeln brauchen sie mit Build-Cache rund drei Minuten.

Platte unter 2G geht nicht: das Droplet belegt 1,1 GB, davon 306 MB `lingua`, 370 MB CPython, 597 MB Pakete. Speicher von `wger-web` über `WEB_CONCURRENCY` steuern; der Bedarf je zusätzlichem Gunicorn-Worker ist nicht gemessen, vor einer Erhöhung an `cf app wger-web` ablesen.

## Hinweise
- Das CF-Dateisystem ist flüchtig: keine lokalen Uploads.
- Stemcells sind BOSH-Plattformebene, für die App nicht relevant. Die App läuft auf dem Root-Filesystem der Plattform (z. B. `cflinuxfs4`).
