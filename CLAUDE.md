# CLAUDE.md

## Projektziel
wger (Django, Python >= 3.12) soll als reguläre Cloud-Foundry-App mit Buildpacks laufen (kein Docker-Image). Upstream: https://github.com/wger-project/wger

## Regeln
- Arbeitsbranch: `cf-port`. Nicht direkt auf `master` committen.
- Upstream-Code möglichst nicht ändern. CF-spezifische Dateien in `cf/` oder als separates Settings-Overlay ablegen, damit Upstream-Merges einfach bleiben.
- Die Projekt-README liegt unter `cf/README.md`. Die Schrittfolge für die Zielplattform steht in `cf/ANLEITUNG-ZIELPLATTFORM.md`. Die `README.md` im Wurzelverzeichnis gehört Upstream und bleibt unverändert, sonst kollidiert jeder Upstream-Merge an dieser Datei.
- Keine Zugangsdaten, internen Vorgangsnummern, konkreten Einsatzorte/-zeiten oder klassifizierten Informationen ins Repo, in Commits oder Prompts. Beispiele anonymisieren.
- Nichts raten: Wenn etwas unklar oder nicht verifiziert ist, im Code/der Doku als "bitte prüfen" markieren oder nachfragen.
- Lizenz AGPL-3.0-or-later beachten.

## Verfügbare CF-Services
Zielplattformen: zwei, einmal TAS (Tanzu Application Service) und einmal Vanilla-Cloud-Foundry (cf-deployment). Buildpack-Versionen, Stacks und ob der Lifecycle `cnb` geht, können sich unterscheiden und sind je Plattform mit `cf buildpacks`, `cf stacks` und einem Probe-Push mit `--lifecycle cnb` abzulesen. Für beide angenommen, noch nicht gemessen:
- PostgreSQL
- Redis
- S3 (S3-kompatibel)
- Mail/SMTP: ungeklärt

Was sonst über die Zielplattform bekannt ist, stammt aus Gesprächen, nicht aus Messungen in diesem Repo (Stand 2026-11-22, **bitte prüfen**):
- Beim Staging ist kein PyPI-Index erreichbar; das npm-Gegenstück (Mirror) funktioniert. Ein PyPI-Mirror ist beim Plattformteam beantragt. Bis dahin bliebe nur Vendoring (`pip download --only-binary=:all:` nach `vendor/`, der klassische `python_buildpack` installiert von dort), nicht getestet.
- Der klassische `python_buildpack` meldet dort beim Detect `python: command not found`. Die genannte Version 1.8.122 passt zu keinem Tag des Upstreams `cloudfoundry/python-buildpack` (die 1.8-Reihe endet bei 1.8.43, danach 1.9.x, geprüft 2026-11-22), und `bin/detect` des Upstreams ruft kein `python` auf: es prüft nur, ob `requirements.txt`, `setup.py`, `environment.yml` oder `Pipfile` existiert. Version und Herkunft der Meldung sind offen; erst `cf buildpacks` dort ablesen.
- Anonymer Docker-Pull von Standard-Images ist gesperrt. Das trifft den Lifecycle `cnb` in `cf/manifest.yml`: `docker://docker.io/paketobuildpacks/python` würde dort nicht laden. Ohne Registry-Zugang bleibt der klassische `python_buildpack` mit `runtime.txt`.
- Auf der Zielplattform werden `lingua-language-detector` 2.2.0 und `psycopg-binary` 3.3.9 als Wheel aus dem Repo gebraucht (Aussage vom 2026-11-23); sie liegen unter `cf/wheels/`, `requirements.txt` zeigt per `--find-links` dorthin. Warum der dortige Index gerade diese beiden nicht liefert, ist nicht bekannt, **bitte prüfen**.
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
- Zwei Schalter im Makefile: `VARIANT=cnb|buildpack` (Bauweise) und `DETECTOR=lingua|llm` (Spracherkennung). `requirements.txt` zeigt auf die erzeugte `cf/requirements.active.txt`.

Offen: S3-Zweig ungetestet, E-Mail ungeklärt, Beat nur kurz beobachtet, Heroku-CNB als Größenhebel nicht gemessen, und alles unter „Zielplattform" oben. Einzelheiten in `cf/README.md`, Abschnitt „Offen".

## Ressourcen beim Start (gemessen 2026-11-21, cfk8s-platform)

Die Werte stehen in `cf/manifest.yml` und `cf/Makefile`; hier die Begründung, damit niemand sie „zum Sparen" senkt oder blind erhöht.

| Was | Speicher | Platte | Instanzen | Gemessen |
|---|---|---|---|---|
| `wger-web` | 1G | 2G | 1 (2 geprüft) | 280–320 MB belegt mit zwei Gunicorn-Workern und `--preload`; 1,4 GB Platte vom Droplet (2026-11-26, mit Übungsbildern). Staging läuft mit dem App-Speicher, unter 1G nicht erprobt |
| `wger-worker` | 512M | 2G | 1 | 190 MB belegt (gevent, Concurrency 2). 2G Platte, weil es dasselbe Droplet ist |
| `wger-beat` | 256M | 2G | **genau 1** | 160 MB belegt. Zwei Beats feuern geplante Aufgaben doppelt |
| `init`-Task | 2G | 2G | – | mit 1G/1G stirbt die Migration `nutrition.0014` mit Exit 137; mehr als 2G Platte lässt die Plattform für Tasks nicht zu |
| Staging (Plattform) | = App-Speicher, min. 1G | **8G** | – | CNB-Export braucht Layer, Cache-Kopie und beide Archive gleichzeitig; bei 4G räumt Kubernetes den Pod (FINDINGS #36 in `cfk8s-platform`). Wird dort gesetzt, nicht im Manifest |

Reihenfolge beim ersten Start: `secrets`, `s3-dev` (nur lokal), `assets`, `push-web`, `init`, `images-import`, `push` (alles `make -f cf/Makefile …`). Die Apps nacheinander pushen, nicht in einem `cf push -f` für alle drei: parallel laufen sie in den Staging-Timeout von 15 Minuten, einzeln brauchen sie mit Build-Cache rund drei Minuten.

Platte unter 2G geht nicht: das Droplet belegt 1,4 GB (gemessen 2026-11-26, `DETECTOR=lingua`), davon 617 MB Pakete mit 292 MB `lingua`, 370 MB CPython, 189 MB Übungsbilder, 167 MB Wheels, 55 MB `staticfiles/`; Einzelheiten in `cf/README.md` unter „Was gemessen ist". Speicher von `wger-web` über `WEB_CONCURRENCY` steuern; der Bedarf je zusätzlichem Gunicorn-Worker ist nicht gemessen, vor einer Erhöhung an `cf app wger-web` ablesen.

## Spracherkennung: zwei Bauweisen, `DETECTOR=lingua|llm` (entschieden 2026-11-23)

wger prüft beim Anlegen von Übungstexten mit `lingua-language-detector`, ob die Sprache des Textes zur gewählten passt (`wger/exercises/api/validators.py`, `wger/core/api/serializers.py`). Das Paket kostet 170 MB als Wheel und 306 MB installiert. Lokal auf `cfk8s` bleibt lingua (`DETECTOR=lingua`, Vorgabe). Für die Zielplattform, wo genau Wheel und Droplet-Größe das Problem sind, gibt es `DETECTOR=llm`: lingua ist nicht installiert (`cf/requirements.llm.lock.txt`), `cf/shim/lingua/` liefert dem unveränderten Upstream-Code dieselbe Schnittstelle und fragt ein Text-LLM der Plattform über den Dienst `wger-llm`. Beides im Makefile, Einzelheiten in `cf/README.md` unter „Spracherkennung über ein LLM". Upstream-Code wird dafür nicht angefasst.
- `qwen/qwen3.8-27b-fp8` der Zielplattform (Name so genannt, nicht verifiziert) ist der Kandidat für `DETECTOR=llm`: ein Text-LLM mit Chat-Schnittstelle. Nicht gemessen: ob die Schnittstelle OpenAI-kompatibel ist, ob das Modell auf die Anweisung nur den Code liefert, und die Latenz je Speichern. Der Shim ist nur gegen einen Stub gemessen.
- `openai/whisper-large-v3-turbo` der Zielplattform ist **kein Ersatz**: Whisper erkennt Sprache aus Audio und nimmt keinen Text entgegen.
- `intfloat/multilingual-e5-large-instruct` der Zielplattform ist **kein Ersatz**: ein Embedding-Modell liefert Vektoren, keine Sprachbezeichnung, und ist mehrsprachig ausgerichtet, sodass gleichbedeutende Sätze verschiedener Sprachen nahe beieinander liegen. Spracherkennung darauf bräuchte einen eigens trainierten Klassifikator plus Netzaufruf je Validierung. Ob die Plattform es als Endpunkt oder nur als Gewichte anbietet, ist nicht bekannt.
- Beschränkung auf Deutsch und Englisch (`LanguageDetectorBuilder.from_languages(GERMAN, ENGLISH)` statt `from_all_languages()`), gemessen 2026-11-23 lokal, lingua 2.2.0, je ein Prozess: Speicher nach vier Erkennungen 27 MB statt 138 MB; Wheel und Installation bleiben gleich groß, die Modelle aller Sprachen liegen ohnehin bei. Kurze Eingaben werden besser („Kniebeuge" ist mit allen Sprachen „Dutch", mit de+en „German"), fremdsprachige Texte werden aber zwangsweise Deutsch oder Englisch zugeordnet (ein spanischer Satz wird „English"). Für eine Instanz, die nur Deutsch und Englisch führt, ist das ein Gewinn; nicht gebaut, weil es Upstream-Code ändert, und mit `DETECTOR=llm` auf der Zielplattform ohne Belang.

## Identity: IdP/IAM-Anschluss (abgelesen 2026-11-23, nichts davon gemessen)

Upstream bringt drei Wege mit, django-allauth 65.21.1:
- **OIDC/OAuth2 über allauth**, der Standardweg: Provider-Apps über die Umgebungsvariable `WGER_SOCIAL_PROVIDERS` (Liste) einschalten; im installierten allauth liegen u. a. `openid_connect`, `microsoft`, `okta`, `gitlab`, `github`, `google`, `saml`. Für ein Unternehmens-IAM ist `openid_connect` der Kandidat (Keycloak, Entra ID, Authentik, jeder Anbieter mit Discovery). Abhängigkeiten (pyjwt mit crypto, oauthlib, requests) sind im Lockfile. Client-ID, Secret und Server-URL kommen **nicht** aus Settings (keine `SOCIALACCOUNT_PROVIDERS` bei Upstream), sondern als „Social Application" in die Datenbank über den Django-Admin.
- **SAML über allauth**: Provider vorhanden, braucht aber das Extra `python3-saml` (xmlsec, libxml2), das im Lockfile fehlt; als Wheel für `cflinuxfs4` nicht geprüft. Wenn OIDC geht, SAML meiden.
- **Auth-Proxy per Header** (`wger/core/middleware.py`, `AUTH_PROXY_HEADER`, `AUTH_PROXY_TRUSTED_IPS`, `AUTH_PROXY_CREATE_UNKNOWN_USER`, Header für E-Mail und Name): ein vorgeschalteter Proxy authentifiziert, die Middleware loggt ein. Auf CF prüft sie bewusst `REMOTE_ADDR`, und das ist hinter dem Gorouter die Router-Adresse; die vertrauenswürdigen Adressen wären die Router, und der Header dürfte den Router nur vom Proxy aus erreichen. Plattformfrage, vor dem Einsatz klären.

wger ist selbst OIDC-Provider (`allauth.idp.oidc`) für API-Clients wie die Flutter-App; das ersetzt keinen IdP. Empfehlung: `openid_connect` lokal auf `cfk8s` gegen einen Keycloak messen, bevor es in `cf/ANLEITUNG-ZIELPLATTFORM.md` kommt; dort steht bislang nichts zu Identity.

## Plattform: Cloud Foundry, nicht Kubernetes (entschieden 2026-11-26)

wger bleibt eine CF-App. Begründung: Die App ist Web, Worker, Beat plus
PostgreSQL, Broker und Object Storage; dafür reicht der Overlay unter `cf/`,
und Routen, Bindungen, Tasks und Logs stellt die Plattform. Auf Kubernetes
kämen Ingress, TLS, Secrets, Probes, Image-Build, Registry und Upgrades in
unsere Hand. Was auf CF weh tat (flüchtiges Dateisystem, Droplet-Größe,
Staging-Grenzen), ist mit S3 gelöst bzw. Plattformkonfiguration, kein
Architekturproblem. Die Hürden der Zielplattform (kein PyPI beim Staging,
kein anonymer Docker-Pull) treffen Kubernetes genauso.

Neu entscheiden, wenn eines eintritt:
- Das Staging auf der Zielplattform ist nicht hinzubekommen und es gibt
  eine Registry. Dann vorgebautes Image, auf CF (`cf push --docker-image`)
  oder Kubernetes.
- Die Organisation stellt ein verwaltetes Kubernetes mit Image-Pipeline.
- wger braucht etwas, das CF nicht kann: Sidecars, mehr als 2 GB Platte
  für einen Task.

Der Wechsel wäre im Code billig: Upstream liefert Docker-Image und
Helm-Chart, `cf/settings.py` würde zu Umgebungsvariablen.

## Hinweise
- Das CF-Dateisystem ist flüchtig: keine lokalen Uploads.
- Stemcells sind BOSH-Plattformebene, für die App nicht relevant. Die App läuft auf dem Root-Filesystem der Plattform (z. B. `cflinuxfs4`).
