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
| `cf/manifest.yml` | drei Apps: `wger-web`, `wger-worker`, `wger-beat`, Lifecycle `cnb` mit `paketobuildpacks/python` |
| `cf/Makefile` | Export, Asset-Build mit `collectstatic`, Push, Initialisierung |
| `cf/requirements.lock.txt` | `uv export` aus `uv.lock`, mit `gunicorn` aus der Gruppe `docker` |
| `cf/requirements-cf.txt` | was CF zusätzlich braucht: `whitenoise` |
| `requirements.txt`, `.python-version`, `.cfignore` | müssen im Wurzelverzeichnis liegen, weil Buildpacks sie dort suchen. `.python-version` liest der Heroku-CNB, Paketo nimmt `BP_CPYTHON_VERSION` aus dem Manifest |

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

Vorher: `cf target` auf den Ziel-Space. Die Plattform muss den Lifecycle
`cnb` können (`cf push --lifecycle cnb`) und beim Staging mindestens 8 GB
flüchtigen Speicher geben: Der CNB-Export legt Layer, Cache-Kopie und beide
Archive gleichzeitig unter `/tmp` ab, bei 4 GB räumt Kubernetes den
Staging-Pod (auf `cfk8s-platform`: `make cf-staging-disk`). Der klassische
`python_buildpack` geht weiterhin: `lifecycle: cnb` und `buildpacks` im
Manifest ersetzen, `runtime.txt` mit `python-3.13.x` anlegen.

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

- Staging mit `paketobuildpacks/python` (Lifecycle `cnb`), CPython 3.13.18.
  Im Container 1,1 GB: Layer 975 MB, davon CPython 370 MB und Pakete
  597 MB, dazu 78 MB Anwendung mit vorgebautem `staticfiles/`. Droplet
  gepackt 392 MB. Zum Vergleich der klassische `python_buildpack`: 1,5 GB.
- Was die Größe bestimmt und ohne Upstream-Änderung bleibt: `lingua`
  (306 MB, eine Binärdatei mit allen Sprachmodellen, von zwei Serializern
  beim Start importiert), `fontawesomefree` als pip-Paket (87 MB), Pakete
  mit Bytecode (`pip-install` übergibt `--compile` fest), CPython bei Paketo
  mit Testsuite (126 MB) und statischer Bibliothek (47 MB).
- `staticfiles/`: 418 MB mit allem, 55 MB mit den Ausschlussmustern in
  `cf/Makefile`; alle von den Templates referenzierten Dateien vorhanden,
  Startseite und Hash-Dateien antworten 200. `node_modules/` (38 MB) wird
  nicht mehr mitgepusht.
- Am Sample `python-hello` gemessen: `heroku/buildpack-python:7.1.0` baut
  einen Python-Layer von 47 MB (Paketo: 337 MB). Für wger nicht gemessen,
  der Push wurde abgebrochen.
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

## Was Cloud Foundry der App bringt

Gemessen am 2026-11-21 an `wger-web` auf `cfk8s-platform`, Monitor im
Sekundentakt gegen `/api/v2/version/` und die Startseite.

| Fähigkeit | Auf der Plattform | Für wger | Messung |
|---|---|---|---|
| Horizontal skalieren (`cf scale -i N`) | ja | ja, weil Sessions und Login-Sperren in der Datenbank liegen | 2 Instanzen, 10 Aufrufe mit Session, 5/5 auf beide verteilt, alle angemeldet |
| Rolling Deployment (`cf push --strategy rolling`) | ja, mit `--max-in-flight` | ja | 236 Messpunkte, 0 Fehler, Umschaltung 45 s |
| Canary (`--strategy canary`, `--instance-steps`, `cf continue-deployment`) | ja | ja | 2 alte Instanzen plus 1 Canary in der Pause, danach ausgerollt, 71 Messpunkte, 0 Fehler |
| Revisionen und Rücknahme (`cf revisions`, `cf rollback --version N`) | ja | ja, ohne neues Staging | Rollback auf Revision 1 als Canary, Revision 3 angelegt |
| Tasks (`cf run-task`) | ja, maximal 2 GB Platte | ja, für Migrationen, Fixtures, Synchronisation | `init`-Task, siehe oben |
| Health Check `http` | ja | ja, `/api/v2/version/` antwortet ohne Datenbank | Staging und Deployments warten darauf |
| Stoppsignal mit 10 s Frist | ja | Worker beendet sich in 5 s mit Exit 0 und verbindet sich neu | `cf restart wger-worker` |
| `cf ssh`, `cf logs`, `cf events` | ja | ja, alle Prozesse loggen auf stdout | genutzt |
| Container-zu-Container-Netz (`apps.internal`, `cf add-network-policy`) | ja | noch nicht gebraucht; der Weg für einen internen Sprachdienst | nicht gemessen |
| Security Groups | `public_networks` für Staging und Laufzeit | nötig für pip beim Staging und `sync-exercises` zur Laufzeit | Staging lädt von PyPI |
| Autoscaler, Scheduler-Dienst, Log-Drain-Ziel, Route Services | nicht installiert | Beat ersetzt den Scheduler; Autoscaling wäre bei Bedarf nachzurüsten | `cf marketplace`, `cf plugins` |

**Was bei Rolling und Canary zu beachten ist.** Während der Umschaltung
laufen alte und neue Version gleichzeitig gegen dieselbe Datenbank.

- Migrationen dürfen dann nur ergänzen, nichts umbenennen oder löschen;
  Upstream-Migrationen sind das nicht immer. Sicher ist: `init`-Task vor dem
  Push, wenn die Migration abwärtskompatibel ist, sonst `cf push` ohne
  Strategie mit kurzem Ausfall.
- Statische Dateien tragen Hash-Namen aus dem jeweiligen Build. In der
  Überlappung kann eine alte Instanz eine neue Hash-Datei nicht liefern,
  das ergibt ein 404 bei einem Teil der Seitenaufrufe. Mit S3 für
  `staticfiles/` läge beides nebeneinander; ohne S3 hilft nur
  `--max-in-flight 1` und ein kurzes Fenster. Im Monitor war das nicht zu
  sehen, weil er nur HTML und die API abgefragt hat.
- `wger-beat` nicht rollend ausrollen: zwei Beats im Überlappungsfenster
  feuern geplante Aufgaben doppelt. Ohne Strategie pushen, der kurze Ausfall
  ist für Beat belanglos.
- `wger-worker` kann rollend, der Warm Shutdown ist gemessen.

## Offen

- **Staging-Zeit**: Beim gemeinsamen Push aller drei Apps lief Beat in den
  Timeout der Plattform (15 Minuten, `staging.timeout_in_seconds` im
  capi-Chart). Allein gepusht staged Beat in drei Minuten, weil der
  Build-Cache des Worker-Laufs greift. Deshalb beim ersten Mal die Apps
  nacheinander pushen; `make -f cf/Makefile push` tut das.
- **Beat**: ob eine geplante Aufgabe zu ihrer Zeit läuft, ist erst nach einem
  Tag Laufzeit messbar.
- **S3**: kein Angebot auf der lokalen Plattform. Der Zweig in
  `cf/settings.py` ist ungetestet.
- **E-Mail**: Upstream braucht `ENABLE_EMAIL` plus SMTP-Variablen; lokal gibt
  es keinen SMTP-Dienst. Die Zugangsdaten gehören nach `wger-secrets`.
- **Prometheus**: `EXPOSE_PROMETHEUS_METRICS=True` schaltet `/prometheus/metrics`
  frei, unauthentifiziert und pro Prozess. Vor dem Einschalten klären.
- **Heroku-CNB als nächster Hebel**: `heroku/buildpack-python` braucht am
  Sample 290 MB weniger für Python als Paketo. Für wger: im Manifest den
  Buildpack tauschen, `.python-version` liegt schon bereit, dann messen.
- **Größe im Container**: 1,1 GB bei 2 GB Quote. Unter 800 MB geht es nur
  mit einer Upstream-Änderung an `lingua` (306 MB).
- Lizenz: wger steht unter **AGPL-3.0-or-later**; wer die Anwendung Dritten
  über ein Netz anbietet, muss die geänderten Quellen bereitstellen.
