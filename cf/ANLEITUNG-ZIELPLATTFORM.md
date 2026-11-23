# Anleitung für den Agenten auf der Zielplattform

Für wen: ein Agent (oder Mensch) mit `cf`-Zugang zur Zielplattform, einem
Clone dieses Repos auf Branch `cf-port` und einem Arbeitsrechner mit `make`,
`git`, `python3`, `sha256sum`. Ziel: wger läuft dort als drei Apps, ohne
lingua, mit Spracherkennung über das Text-LLM der Plattform.

Stand 2026-11-23. Alles hier ist auf der lokalen Entwicklungsplattform
`cfk8s` oder lokal gemessen, **nichts davon auf der Zielplattform**. Wo eine
Annahme steht, ist sie als solche markiert. Die Aufgabe ist deshalb zur
Hälfte Messen: jedes Ergebnis gehört in `cf/README.md`, als Commit auf
einem Branch ab `cf-port`.

## Regeln

1. **Nichts raten.** Was nicht gemessen ist, wird als „bitte prüfen"
   notiert, nicht als Tatsache. Ein Push, der durchgeht, ist eine Messung;
   ein Log, das etwas sagt, ist eine Messung; eine Vermutung ist keine.
2. **Keine Geheimnisse ins Repo, in Commits oder in den Chat.** Keine
   Tokens, URLs interner Endpunkte, Hostnamen, Vorgangsnummern. Credentials
   kommen ausschließlich über `cf create-user-provided-service` in Bindungen.
   In die Doku kommt die Form, nicht der Wert.
3. **Upstream-Code nicht ändern.** Alles CF-Spezifische liegt unter `cf/`
   oder in den vier Wurzeldateien `requirements.txt`, `runtime.txt`,
   `.python-version`, `.cfignore`. Wer etwas in `wger/` ändern müsste, hält
   an und schreibt auf, warum.
4. **Aufruf immer aus dem Wurzelverzeichnis:** `make -f cf/Makefile <ziel>`.
5. **Reihenfolge einhalten.** Erst messen (Schritt 1), dann entscheiden,
   dann pushen. Die Apps nacheinander, nie alle drei in einem `cf push`.

## Schritt 1: Plattform messen

Vor jeder Änderung. Ausgaben anonymisiert festhalten (Versionen ja, Hostnamen
nein).

```
cf target                         # Org und Space
cf stacks                         # cflinuxfs4 muss dabei sein
cf buildpacks                     # Name und Version des Python-Buildpacks
cf marketplace                    # PostgreSQL, Redis, S3, Mail, LLM?
```

Zu klären, je eine Zeile Antwort:

- Gibt es `cflinuxfs4`? Ohne ihn passen die Wheels unter `cf/wheels/` nicht
  (x86_64, glibc 2.35).
- Wie heißt der Python-Buildpack genau, welche Version, und welche
  CPython-Versionen liefert er? Bei einem Offline-Buildpack stehen sie in
  seiner `manifest.yml`; sonst muss er `buildpacks.cloudfoundry.org`
  erreichen. `runtime.txt` sagt `python-3.13.x`. Bietet er kein 3.13:
  `runtime.txt` und `.python-version` auf die höchste Version ab 3.12 setzen
  und das als Messung notieren.
- Erreicht das Staging einen PyPI-Index oder Mirror? Messung: ein Push einer
  App mit `VARIANT=buildpack` ohne `vendor/` (Schritt 5), dann im Staging-Log
  nach „Running Pip Install (Unvendored)" und dem, was danach kommt, sehen.
- Wie wird das LLM angeboten: als HTTP-Endpunkt mit welchem Pfad, welcher
  Authentifizierung? Siehe Schritt 3.

## Schritt 2: Dienste anlegen

```
cf create-service <postgres-angebot> <plan> wger-db
cf create-service <redis-angebot> <plan> wger-redis     # falls es Redis gibt
cf create-service <rabbitmq-angebot> <plan> wger-mq     # sonst RabbitMQ
make -f cf/Makefile secrets                              # wger-secrets mit SECRET_KEY
```

Gibt es Redis, nimmt `cf/settings.py` es für Cache, Sessions und als
Celery-Broker; dann entfällt `wger-mq`, und im Manifest ist bei allen drei
Apps `wger-mq` durch `wger-redis` zu ersetzen. Gibt es beides, reicht Redis.
Die Erkennung läuft über Tags der Bindung (`postgresql`, `redis` oder
`valkey`, `amqp`) oder über den Instanznamen; welche Tags der dortige Broker
vergibt, mit `cf env wger-web` nach dem ersten Push ablesen.

Die Bindung der Datenbank muss `uri` oder `fqdn-uri` tragen oder die Felder
`host`, `port`, `username`, `password`, `dbname`. Andere Schlüsselnamen:
in `cf/settings.py` ergänzen, Abschnitt „Datenbank", mit Kommentar.

## Schritt 3: Das LLM prüfen und binden

Angenommen ist eine OpenAI-kompatible Chat-API: `POST {url}/chat/completions`
mit JSON-Body und `Authorization: Bearer <token>`. **Das ist nicht gemessen.**
Erst mit `curl` prüfen, mit dem Modell, das `cf marketplace` oder die
Plattformdoku nennt (genannt wurde `qwen/qwen3.8-27b-fp8`, Schreibweise
nicht verifiziert):

```
curl -sS "$URL/chat/completions" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{
  "model": "<modellname>", "temperature": 0, "max_tokens": 5,
  "messages": [
    {"role": "system", "content": "Identify the language of the text given by the user. Reply with the ISO 639-1 code only: exactly two lowercase letters, nothing else. If the language cannot be determined, reply with xx."},
    {"role": "user", "content": "Die Kniebeuge ist eine Grundübung für die Beine."}
  ]}'
```

Festzuhalten:

- Antwortet der Endpunkt im OpenAI-Format (`choices[0].message.content`)?
  Wenn nicht: `cf/shim/lingua/__init__.py`, Methode `_ask`, an das
  Format anpassen. Das ist die einzige Stelle.
- Steht in `content` genau `de`? Oder etwas wie `Die Sprache ist Deutsch`?
  Im zweiten Fall gilt die Antwort als „nicht erkannt", und jedes Speichern
  einer Übung scheitert. Dann die Anweisung `_PROMPT` im Shim anpassen,
  bis das Modell nur den Code liefert, und die gemessenen Antworten notieren.
- Antwort auf `Kniebeuge` allein und auf `The squat is a basic exercise.`
- Dauer eines Aufrufs (`curl -w '%{time_total}'`). Sie liegt künftig auf
  jedem Speichern einer Übung. Über zwei Sekunden: notieren und melden.
- Ob Qwen „Denk"-Text liefert (Felder wie `reasoning_content` oder
  `<think>`-Blöcke in `content`): dann `max_tokens` im Shim erhöhen und
  den Block vor dem Parsen entfernen, oder den Thinking-Modus über die API
  abschalten, falls sie das anbietet. Gemessen ist das nicht.

Dann den Dienst anlegen. `url` ist die Basis **ohne** `/chat/completions`:

```
cf create-user-provided-service wger-llm \
  -p '{"url": "https://<endpunkt>/v1", "model": "<modellname>", "api_key": "<token>"}'
```

`wger-llm` muss bei allen drei Apps gebunden sein. Entweder im Manifest bei
jeder App unter `services:` eintragen (dann kommt die Bindung mit dem Push),
oder nach dem Push `cf bind-service <app> wger-llm` und `cf restage`.

## Schritt 4: Was auf dem Arbeitsrechner vorliegen muss

`staticfiles/` (rund 55 MB) muss vor dem Push im Wurzelverzeichnis liegen;
die Apps liefern Static-Files daraus, und es ist nicht im Repo. Es entsteht
mit `make -f cf/Makefile assets`, und das braucht `uv` mit einer
funktionierenden Umgebung (`uv sync`, also PyPI) sowie `npm` mit Registry
oder Mirror. Zwei Wege:

- Der Arbeitsrechner erreicht PyPI und npm: `uv sync`, dann
  `make -f cf/Makefile assets`.
- Er erreicht es nicht: `staticfiles/` auf einem Rechner mit Zugang bauen
  und als Archiv herüberbringen. Entpackt muss es `staticfiles/` im
  Wurzelverzeichnis sein, mit `staticfiles/staticfiles.json` darin.

Dasselbe gilt für `vendor/` in Schritt 5, falls es gebraucht wird:
`make -f cf/Makefile vendor DETECTOR=llm` lädt mit `pip` von PyPI.

Die zwei Wheels unter `cf/wheels/` brauchen nichts: `make -f cf/Makefile
wheels DETECTOR=llm` prüft nur die Prüfsumme von `psycopg-binary` und
lässt die lingua-Teile liegen.

## Schritt 5: Bauen und pushen

Die Vorgabe für die Zielplattform ist `VARIANT=buildpack DETECTOR=llm`:
klassischer `python_buildpack`, weil kein Registry-Zugang für das
Paketo-Image angenommen ist; ohne lingua, weil Wheel und Droplet-Größe dort
das Problem sind. Beide Werte bei **jedem** `make`-Aufruf mitgeben.

```
export V="VARIANT=buildpack DETECTOR=llm"
make -f cf/Makefile requirements $V      # schreibt cf/requirements.active.txt ohne lingua
make -f cf/Makefile wheels $V            # nur psycopg-binary, Pruefsumme
make -f cf/Makefile push-web $V          # erster Push, nur wger-web
```

Wie die Pakete beim Staging kommen, nach Messung aus Schritt 1:

- Index oder Mirror erreichbar: nichts tun, bzw. bei einem Mirror
  `--index-url <mirror>` als erste Zeile in `requirements.txt`. Die Zeile
  `--find-links cf/wheels` bleibt; von dort kommt `psycopg-binary`.
- Kein Index: `vendor/` muss im Push liegen (Schritt 4). Dann installiert
  der Buildpack mit `--no-index` nur daraus; im Staging-Log steht
  „Running Pip Install (Vendored)".

Nach dem ersten Push ablesen und notieren:

```
cf app wger-web                   # Zustand, Speicher, Platte
cf logs wger-web --recent         # Staging: Buildpack-Version, Python-Version, Pip-Zeile
cf env wger-web                   # Tags und Schluesselnamen der Bindungen (Werte NICHT notieren)
```

Erwartet, nicht gemessen: Platte deutlich unter 1,1 GB, weil lingua fehlt.
Dann:

```
make -f cf/Makefile init $V              # Migrationen, Fixtures, admin, Cache-Tabelle, Site-URL
make -f cf/Makefile push $V              # alle drei Apps, nacheinander
```

`init` legt `admin` mit Passwort `adminadmin` an. **Sofort ändern.**

Terminiert die Plattform TLS für App-Routen, die Zeilen
`WGER_SITE_SCHEME: http` im Manifest bei allen drei Apps entfernen; die
Vorgabe ist dann `https`.

## Schritt 6: Die Spracherkennung messen

Die Validierung läuft beim Anlegen einer Übung. Als eingeloggter Nutzer in
der Web-Oberfläche eine Übung mit deutscher Beschreibung und Sprache
Deutsch anlegen, dann dieselbe mit englischer Beschreibung und Sprache
Deutsch. Oder über die API: API-Schlüssel in der Web-Oberfläche unter
`/<sprache>/user/api-key` erzeugen (Pfad mit Sprachpräfix, etwa `/de/`),
Header `Authorization: Token <schlüssel>`, dann der Sprachcheck-Endpunkt
`POST /api/v2/check-language/` oder `/api/v2/exercise-translation/`;
Feldnamen in `wger/core/api/serializers.py`. Es gibt keinen
Login-Endpunkt `/api/v2/login/`; `/api/v2/token/refresh` und `/verify`
gehören zu JWT und brauchen ein vorhandenes Token.

Erwartet:

| Eingabe | Erwartet |
|---|---|
| deutscher Text, Sprache Deutsch | wird gespeichert |
| englischer Text, Sprache Deutsch | Fehler „The detected language … is English (en)" |
| ein Wort („Kniebeuge") | je nach Modell; notieren |
| LLM-Dienst nicht erreichbar | HTTP 500, im Log `LLM-Spracherkennung fehlgeschlagen` |

Dazu `cf logs wger-web` mitlaufen lassen: der Shim loggt jede Antwort, die er
nicht als Code lesen konnte (`ohne Ergebnis, Antwort: …`). Erscheint das bei
jeder Eingabe, liefert das Modell nicht nur den Code, zurück zu Schritt 3.

## Schritt 7: Zurückmelden

Ein Branch ab `cf-port`, ein oder mehrere Commits, Nachrichten auf Deutsch.
Hinein gehört, in `cf/README.md`:

- Die Messungen aus Schritt 1 (Stack, Buildpack mit Version, verfügbare
  Python-Versionen, Index ja oder nein, Dienste mit Angebotsnamen und Tags),
  ohne Hostnamen und ohne Werte.
- Aus Schritt 3: Format der LLM-Antworten, die vier gemessenen Antworten,
  die Dauer je Aufruf, ob die Anweisung geändert werden musste.
- Aus Schritt 5: Speicher und Platte je App nach `cf app`, Staging-Dauer.
- Aus Schritt 6: die Tabelle, ausgefüllt.
- Jeden Punkt, der in dieser Anleitung oder in `cf/README.md` als „bitte
  prüfen" steht und jetzt gemessen ist: die Markierung entfernen und den
  gemessenen Wert hinschreiben. Was sich als falsch erwiesen hat, nicht
  als Historie beschreiben, sondern ersetzen; die Historie steht im Commit.

Was nicht ging, gehört genauso hinein, mit der Fehlermeldung im Wortlaut.

## Rückfall

Liefert das LLM keine brauchbaren Antworten oder gibt es keinen Endpunkt:
`DETECTOR=lingua`. Dann setzt `make wheels` das lingua-Wheel aus den Teilen
unter `cf/wheels/` zusammen, es geht mit in den Push, und die
Spracherkennung läuft lokal wie bei Upstream. Kosten: 170 MB im Upload und
Droplet plus 306 MB installiert; die Plattenquote von 2G im Manifest
reicht dafür nach lokaler Messung, mit wenig Reserve.
