# wger auf Cloud Foundry

Portierung von [wger](https://github.com/wger-project/wger) (Workout-,
Ernährungs- und Gewichts-Tracker, Django) auf **Cloud Foundry** mit
Buildpacks statt Docker-Image. Dieses Repo ist ein Abzweig von
`wger-project/wger`; die Upstream-README liegt im Wurzelverzeichnis.

> Stand 2026-11-21: läuft auf der lokalen Entwicklungsplattform
> `cfk8s-platform` (echtes Cloud Foundry auf kind). Alles unten ist dort
> gemessen, sofern nicht als „bitte prüfen" markiert.

## Was wo liegt

| Datei | Zweck |
|---|---|
| `cf/settings.py` | Settings-Overlay: übersetzt `VCAP_SERVICES` in die Variablen, die `settings/main.py` liest, und importiert es danach |
| `cf/storage.py` | whitenoise-Storage mit der Nachsicht von Upstream gegenüber fehlenden Source Maps |
| `cf/manifest.yml` | drei Apps: `wger-web`, `wger-worker`, `wger-beat` |
| `cf/Makefile` | Export, Asset-Build, Push, Initialisierung |
| `cf/requirements.lock.txt` | `uv export` aus `uv.lock`, mit `gunicorn` aus der Gruppe `docker` |
| `cf/requirements-cf.txt` | was CF zusätzlich braucht: `whitenoise` |
| `requirements.txt`, `runtime.txt`, `.cfignore` | müssen im Wurzelverzeichnis liegen, weil der Buildpack sie dort sucht |

Upstream-Dateien sind nicht verändert; `.gitignore` hat vier Zeilen für
erzeugte Dateien bekommen.

## Dienste

| Dienst | Instanz | Bindung in `cf/settings.py` |
|---|---|---|
| PostgreSQL (`cnpg-postgresql`, Plan `small`) | `wger-db` | Tag `postgresql`; Host aus `fqdn-uri`, weil `host` dort ein kurzer Service-Name ohne Namespace ist |
| RabbitMQ (`rabbitmq-cluster`, Plan `dev`) | `wger-mq` | Tag `amqp`; Celery-Broker, Ergebnis-Backend `rpc://` |
| benutzerdefiniert | `wger-secrets` | Name; `secret_key`, optional `jwt_public_key`, `jwt_private_key`, `email_host_user`, `email_host_password` |
| Redis (Tag `redis` oder `valkey`) | – | wenn gebunden: Cache, Sessions, Celery-Broker. Lokal nicht vorhanden |
| S3 (Tag `s3`) | – | wenn gebunden: Media-Uploads. Lokal nicht vorhanden; **bitte prüfen**, die Schlüsselnamen der Credentials sind geraten |

**Ohne Redis** liegen Cache, Sessions (`cached_db`) und die Login-Sperren
von django-axes in der Datenbanktabelle `wger_cache`. **Ohne S3** landen
Uploads im flüchtigen Dateisystem und sind nach einem Neustart weg.

## Erster Start

Vorher: `cf target` auf den Ziel-Space, `python_buildpack` vorhanden
(`cf buildpacks`; auf `cfk8s-platform`: `make cf-buildpack-python`).

```
cf create-service cnpg-postgresql small wger-db
cf create-service rabbitmq-cluster dev wger-mq
make -f cf/Makefile secrets      # wger-secrets mit zufaelligem SECRET_KEY
make -f cf/Makefile assets       # node_modules/ (38 MB) und bootstrap-compiled.css
make -f cf/Makefile push-web     # nur wger-web; Staging mit collectstatic
make -f cf/Makefile init         # Migrationen, Fixtures, admin, Cache-Tabelle, Site-URL
make -f cf/Makefile push         # alle drei Apps
```

`init` legt den Benutzer `admin` mit dem Passwort `adminadmin` an (Upstream-
Verhalten von `wger bootstrap`). **Danach ändern.**

## Was gemessen ist

- Staging mit `python_buildpack` 1.9.4, Python 3.13.15, `collectstatic` beim
  Staging: 11 421 Dateien, Droplet 1,5 GB von 2 GB Platte. Der Löwenanteil
  ist `fontawesomefree` (272 MB), das Upstream als pip-Paket mitbringt.
- Healthcheck `http` auf `/api/v2/version/`: antwortet ohne Anmeldung mit 200
  und der Version, ohne Datenbank.
- Statische Dateien mit Hash-Namen aus whitenoise: 200, richtiger Content-Type.
- `init` als Task braucht 2 GB Speicher und 2 GB Platte: mit dem Standard
  (1 GB) starb die Migration `nutrition.0014` mit Exit 137, und mehr als 2 GB
  Platte lässt die Plattform nicht zu.
- Login über die Route: `POST /en/user/login` antwortet 302, Session-Cookie
  gesetzt, Dashboard zeigt den Benutzer. CSRF hinter dem Gorouter funktioniert,
  `X-Forwarded-Proto` wird ausgewertet.
- Worker: verbindet sich mit dem RabbitMQ-Broker und meldet `ready`. Ein per
  `celery --app wger call` abgeschickter Task wurde im Worker empfangen und
  als `succeeded` protokolliert. Beat startet mit `PersistentScheduler` auf
  `/tmp/celerybeat-schedule`.

## Betrieb

| Aufgabe | Befehl |
|---|---|
| Logs | `cf logs wger-web --recent` (alle Prozesse loggen auf stdout) |
| Migration nach einem Update | `make -f cf/Makefile init` (idempotent; `bootstrap` migriert nur, Fixtures lädt es nur bei leerer DB) |
| Übungsdaten nachladen | `cf run-task wger-web -m 2G -k 2G --command "python manage.py sync-exercises"` (braucht ausgehendes Internet) |
| Zutaten nachladen | `cf run-task wger-web -m 2G -k 2G --command "python -m wger load-online-fixtures"` |
| JWT-Schlüssel | `cf run-task wger-web --command "python manage.py generate-jwt-keys"`, Ausgabe nach `wger-secrets` (`cf update-user-provided-service`) |
| Abhängigkeiten nach Upstream-Merge | `make -f cf/Makefile export`, dann `assets`, dann `push` |

Die Route ist lokal nur per HTTP erreichbar; `WGER_SITE_SCHEME: http` im
Manifest sagt das der App. Auf einer Plattform mit TLS-Terminierung entfällt
die Zeile.

## Offen

- **Beat** läuft, aber ob eine geplante Aufgabe zu ihrer Zeit auch ausgeführt
  wird, ist erst nach einem Tag Laufzeit messbar.
- **S3**: kein Angebot auf der lokalen Plattform. Der Zweig in
  `cf/settings.py` ist ungetestet.
- **E-Mail**: Upstream braucht `ENABLE_EMAIL` plus SMTP-Variablen; lokal gibt
  es keinen SMTP-Dienst. Die Zugangsdaten gehören nach `wger-secrets`.
- **Prometheus**: `EXPOSE_PROMETHEUS_METRICS=True` schaltet `/prometheus/metrics`
  frei, unauthentifiziert und pro Prozess. Vor dem Einschalten klären.
- **Plattenplatz**: 1,5 GB Droplet bei 2 GB Quote. Wächst `fontawesomefree`
  oder `node_modules`, scheitert das Staging an der Platte.
- Lizenz: wger steht unter **AGPL-3.0-or-later**; wer die Anwendung Dritten
  über ein Netz anbietet, muss die geänderten Quellen bereitstellen.
