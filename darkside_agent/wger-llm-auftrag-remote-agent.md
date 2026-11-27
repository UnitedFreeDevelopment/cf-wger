# Auftrag: LLM-Spracherkennung für wger anbinden (<LLM_DIENST> via CF-Dienst `wger-llm`)

**Auftraggeber:** <AUFTRAGGEBER>
**Durchführung:** Remote Agent
**Stand der Fakten:** 27.11.2026 (alle Angaben unten dann verifiziert; Abweichungen → melden, nicht still korrigieren)

## Platzhalter: vor dem Ausführen ersetzen, nie zurückschreiben

Diese Datei ist anonymisiert, damit sie im Repo liegen darf. Alles in spitzen
Klammern ist ein Platzhalter. Der Agent setzt die echten Werte **vor dem
Ausführen** aus seiner Umgebung ein (Spalte „Quelle") und schreibt sie **nie**
in diese Datei, in Berichte unter `cf/berichte/`, in Logs oder in Chats zurück.
Ein Report nennt Werte nur als Platzhalter oder gar nicht. Fehlt ein Wert,
anhalten und beim Auftraggeber nachfragen, nicht raten.

| Platzhalter | Bedeutung | Quelle |
|---|---|---|
| `<AUFTRAGGEBER>`, `<AUFTRAGGEBER_EMAIL>`, `<AUFTRAGGEBER_EINHEIT>` | Wer den Auftrag gibt, Absender des FW-Wunschtexts | getrennt übergeben |
| `<ORGANISATION>` | Die Organisation, die Plattform und VDI betreibt | getrennt übergeben |
| `<PLATTFORMTEAM>` | Anrede des Teams, das die Firewall-Freigabe erteilt | getrennt übergeben |
| `<CF_API>`, `<CF_API_HOST>` | CF-API der Zielplattform, mit und ohne `https://` | getrennt übergeben; nach Login mit `cf target` gegenprüfen |
| `<CF_ORG>`, `<CF_SPACE>`, `<FOUNDATION>` | Org, Space und Foundation der App | getrennt übergeben; `cf target` |
| `<APP_ROUTE>` | Route von `wger-web` | `cf apps` nach dem Login |
| `<CF_SVC_ACCOUNT>` | Name des CF-Service-Users (headless) | gopass, s. u. |
| `<GOPASS_CF_USER>`, `<GOPASS_CF_PASSWORD>` | gopass-Pfade zu Benutzer und Passwort des Service-Users | getrennt übergeben; Werte bleiben in gopass |
| `<LLM_DIENST>` | Interner Name des Text-LLM-Angebots | getrennt übergeben |
| `<LLM_URL>`, `<LLM_HOST>` | Basis-URL der OpenAI-kompatiblen API (mit `/v1`) und ihr Hostname für den FW-Text | getrennt übergeben; `GET <LLM_URL>/models` gegenprüfen |
| `<VDI_HOST>`, `<VDI_USER>` | Rechner und Kennung, von denen der Endpunkt erreichbar war (nur Beleg für den FW-Text) | getrennt übergeben |

Nicht ersetzt, weil kein Geheimnis und keine interne Struktur: App-Namen
(`wger-web`, `wger-llm`), der Modellname `qwen3.8-27b` (wird in 3a ohnehin
abgelesen) und alle Dateinamen des Repos.

## Ziel

Die Cloud-Foundry-App **wger-web** auf der <ORGANISATION>-PaaS (Org `<CF_ORG>`, Space `<CF_SPACE>`,
API `<CF_API>`) soll statt des lokalen lingua-Modells
(170 MB im Droplet) das Text-LLM **<LLM_DIENST>** (OpenAI-kompatible vLLM-API) für die
Spracherkennung von Übungstexten nutzen. Anbindung als **user-provided CF-Service
`wger-llm`** (entspricht dem Design in `cf/README.md` des Repos). Die Lingua-Variante
bleibt jederzeit zurückschaltbar.

## Verifizierte Fakten (27.11.2026)

- **<LLM_DIENST>-Endpunkt:** `<LLM_URL>` (OpenAI-kompatibel;
  `GET /v1/models` → Modell-ID **`qwen3.8-27b`**, max. Kontext 262144). **Keyless**
  (ohne Auth getestet). Falls in deiner Umgebung ein <LLM_DIENST>-Token erforderlich ist:
  `api_key` in das Service-Payload aufnehmen (Wert über gopass/Secretshare — **nie
  in Reports, Logs oder Chats**).
- **App-Code:** `cf/settings.py` prüft die Env-Variable `WGER_LANGUAGE_DETECTOR`
  (Default `lingua`). Bei Wert `llm`: (1) `cf/shim` wird vor die site-packages
  gelegt (Shim = Drop-in-Ersatz für das `lingua`-Paket mit exakt der API, die
  `wger/exercises/api/validators.py` und `wger/core/api/serializers.py` nutzen),
  (2) aus der Service-Bindung `wger-llm` (Name oder Tag `llm`) werden
  `WGER_LLM_URL` / `WGER_LLM_API_KEY` / `WGER_LLM_MODEL` gesetzt.
  Der Shim ruft `POST {WGER_LLM_URL}/chat/completions` auf (Temperature 0, ≤ 5
  Tokens, Erwartung: genau ein 2-stelliger ISO-639-1-Code, sonst `xx`/Fehler).
- **Zurückschalten ohne Rebuild möglich:** Env-Variable + `cf restart` genügen
  (der Shim greift auch bei installiertem lingua, weil `cf/settings.py` ihn beim
  Laden der Settings in `sys.path` vorzieht; die Variable wird zur Laufzeit
  gelesen, am Build hängt nichts davon ab). `cf restage` ist NICHT nötig und
  auf der Zielplattform zu meiden: Staging dort läuft ohne PyPI in den
  15-Minuten-Timeout. Ein eigener `DETECTOR=llm`-Build (ohne lingua,
  306 MB weniger im Droplet) ist die spätere Optimierungsstufe, KEINE
  Voraussetzung für diesen Auftrag.
- **Hilfsskript für `cf ssh`:** `cf/appenv.sh` im Repo gibt einer SSH-Sitzung
  PATH, PYTHONPATH, LD_LIBRARY_PATH und Arbeitsverzeichnis des laufenden
  App-Prozesses (ohne das gibt es dort kein `python`). Die Pfade unter
  `/home/vcap/deps/…` sind bauweisenabhängig, das Skript nicht.
- **Variablen `WGER_LLM_*` sind nur im Python-Prozess sichtbar:**
  `cf/settings.py` setzt sie per `os.environ.setdefault` aus der Bindung. In
  einer `cf ssh`-Shell sind sie LEER; das ist kein Fehler. Prüfen über
  `cf env` (Bindung) bzw. in Python nach `django.setup()`.
- **Netz-Status (gemessen 27.11.2026, aus dem wger-web-Container):**
  `curl -k -m 20 <LLM_URL>/models` →
  **Connection timeout** → der Pfad PaaS → SaaS ist (noch) FW-blockiert.
  Von der <ORGANISATION>-VDI (Host `<VDI_HOST>`, User `<VDI_USER>`) ist derselbe
  Endpunkt erreichbar. **Solange der Pfad zu, sind Schritte 4–6 nicht ausführbar**
  (Schritte 1–3 dürfen vorbereitet werden, aber nicht gegen das Live-System
  setzen, bis Schritt 3a grün ist).
- **Zugangsdaten:** CF-Service-User für headless-Betrieb (Name/PW in gopass
  `<GOPASS_CF_USER>` bzw. `<GOPASS_CF_PASSWORD>`, Account `<CF_SVC_ACCOUNT>`,
  Rolle SpaceDeveloper in <CF_ORG>/<CF_SPACE>). <LLM_DIENST>: keyless (s. o.). **Kein Wert
  dieses Dokuments ist ein Secret; alle Secrets verbleiben in gopass.**
- **Betrifft:** nur `wger-web` (Spracherkennung läuft im Web-API-Pfad;
  `wger-worker`/`wger-beat` binden wir NICHT — sie behalten das echte lingua,
  das in dem Build installiert ist).

## Arbeitsschritte

### 1) Zugang aufbauen
```
cf api --skip-ssl-validation <CF_API>
cf login -u <gopass: <GOPASS_CF_USER>> -p <gopass: <GOPASS_CF_PASSWORD>>
cf target -o <CF_ORG> -s <CF_SPACE>
cf apps            # muss wger-web (started 1/1, Route <APP_ROUTE>) zeigen
```
(Ältere cf-Build-Quirks: `cf whoami` gibt es nicht → `cf target` zeigt die Session.
`cf curl` nimmt keine curl-Flags wie `-s` an.)

### 2) Dienst anlegen (idempotent)
```
cf services | grep -i wger-llm        # existiert er schon? dann überspringen
cf create-user-provided-service wger-llm \
  -p '{"url": "<LLM_URL>", "model": "qwen3.8-27b"}'
```
(`api_key` weggelassen, da keyless — nur ergänzen, falls in deiner Umgebung ein
Token erforderlich ist.)

### 3) Binden + Umschalten
```
cf bind-service wger-web wger-llm
cf set-env wger-web WGER_LANGUAGE_DETECTOR llm
cf restart wger-web                    # kurze Unterbrechung; KEIN restage (s. Fakten)
```

### 3a) NETZ-PRÜFUNG (entscheidend, vor 4–6)
Zweimal: erst mit `-k`, dann OHNE. Der Shim prüft Zertifikate (requests-Standard);
eine Firewall-Freigabe allein reicht nicht, wenn der Endpunkt ein Zertifikat einer
internen CA trägt.
```
cf ssh wger-web --command 'curl -sS -k -m 20 <LLM_URL>/models | head -c 400'
cf ssh wger-web --command 'curl -sS    -m 20 <LLM_URL>/models | head -c 400'
```
- **Beide 200 + JSON (Modell `qwen3.8-27b`)** → weiter mit 4.
- **Timeout / Connection refused** → FW-Regel fehlt. Dann: ALLES ROLLBACKEN
  (Schritt 7), den unten angehängten **FW-Wunschtext** ausliefern und ANHALTEN.
  Nicht im Halbzustand (gebundener Dienst, Env auf llm) lassen.
- **Mit `-k` 200, ohne `-k` Zertifikatsfehler** (`SSL certificate problem`,
  `unable to get local issuer certificate`) → kein FW-Thema. ROLLBACKEN
  (Schritt 7), als eigenen Fall „Zertifikat/CA" melden (Aussteller aus
  `curl -v` nennen, kein FW-Wunschtext) und ANHALTEN. Den Shim auf
  `verify=False` zu stellen ist NICHT Teil dieses Auftrags.

### 4) Bindung und Schalter prüfen
NICHT per `cf ssh … echo $WGER_LLM_URL`: die Variablen setzt `cf/settings.py`
nur im Python-Prozess, in der SSH-Shell sind sie immer leer (s. Fakten).
```
cf env wger-web | grep -E '"name": "wger-llm"|"url"|"model"'
cf env wger-web | grep WGER_LANGUAGE_DETECTOR
```
Erwartet: ein Eintrag `"name": "wger-llm"` mit `"url": "<LLM_URL>"`
und `"model": "qwen3.8-27b"`; darunter `WGER_LANGUAGE_DETECTOR: llm`.
**Nie die ganze `cf env`-Ausgabe in den Report**: sie enthält alle Credentials
(Datenbank, ggf. `api_key`). Nur die gefilterten Zeilen, ohne `api_key`.

### 5) Erste ECHTE LLM-Messung (Shim-Doku: „nicht gemessen, bitte prüfen")
Direktprobe (erwartet: genau `de`):
```
cf ssh wger-web --command 'curl -sS -m 60 -X POST "<LLM_URL>/chat/completions" -H "Content-Type: application/json" -d "{\"model\": \"qwen3.8-27b\", \"messages\": [{\"role\": \"user\", \"content\": \"Identify the language of the text given by the user. Reply with the ISO 639-1 code only: exactly two lowercase letters, nothing else. If the language cannot be determined, reply with xx. — Guten Tag, ich bin heute trainieren.\"}], \"temperature\": 0, \"max_tokens\": 5}"'
```
Zweitprobe (erwartet: `en`): Text „Good morning, I went to the gym today."

### 6) End-to-End durch den Shim (das eigentliche Abnahmekriterium)
Im Web-Container den exakten Code-Pfad testen, den die App nutzt (Upstream-Import).
**Zwingend zuerst `django.setup()`**: erst das Laden von `cf.settings` legt
`cf/shim` in den `sys.path`. Ein nacktes `python -c "from lingua import …"`
trifft das installierte echte lingua und liefert die erwarteten Werte AUCH OHNE
LLM: falsches GRÜN. Die SSH-Sitzung bringt `DJANGO_SETTINGS_MODULE=cf.settings`
und `WGER_LANGUAGE_DETECTOR=llm` aus dem Manifest bzw. `set-env` mit;
`cf/appenv.sh` liefert PATH und Arbeitsverzeichnis des laufenden Prozesses.
```
cf ssh -T wger-web -c 'APP=$(readlink /proc/$(pgrep -o -f gunicorn)/cwd); cat > /tmp/probe.py <<EOF
import django
django.setup()
import lingua
from lingua import LanguageDetectorBuilder
print("modul:", lingua.__file__)
d = LanguageDetectorBuilder.from_all_languages().build()
print("konfidenzen:", d.compute_language_confidence_values("Guten Tag"))
for t in ["Guten Tag, ich bin heute trainieren.", "Good morning, I went to the gym today.", "Bonjour, je suis allé à la salle de sport."]:
    r = d.detect_language_of(t)
    print(r.iso_code_639_1.name, r.name)
EOF
"$APP/cf/appenv.sh" python /tmp/probe.py'
```
Erwartet, in dieser Reihenfolge:
- `modul: …/cf/shim/lingua/__init__.py` (NICHT `…/site-packages/lingua/…`)
  → beweist, dass der Shim und nicht lingua antwortet.
- `konfidenzen: []` → zweiter Beweis: der Shim liefert keine Verteilung, das
  echte lingua liefert eine Liste von Werten.
- `DE GERMAN`, `EN ENGLISH`, `FR FRENCH` (ISO-Code bei lingua wie beim Shim in
  Großbuchstaben).
Zeigt `modul:` auf site-packages → Schalter greift nicht (Env-Variable prüfen,
Schritt 4) → Melden, nicht weiterwerten.
- Antwort kommt, aber nicht als 2-Buchstaben-Code → <LLM_DIENST>-Modell verhält sich
  anders als der Stub → Melden (Prompt-Tuning wäre Folgeauftrag, nicht jetzt).
- `LanguageDetectionUnavailable` / HTTP-Fehler → LLM antwortet nicht → Melden
  (Netz/Akzeptanz des Endpunkts).
- **Nicht** mit echten Benutzerdaten testen (keine Saves über die API).

### 7) Rollback (falls rot, oder wenn <AUFTRAGGEBER> es will)
```
cf unset-env wger-web WGER_LANGUAGE_DETECTOR
cf restart wger-web                    # restart reicht, kein restage
# optional (Dienst komplett entfernen):
cf unbind-service wger-web wger-llm
cf delete-service wger-llm -f
```
Rollback = Lingua-Betrieb wie vorher (keine Daten-/Konfig-Auswirkung darüber hinaus).

### 8) Report (an <AUFTRAGGEBER>, zwei Teile)
**a) Kurzfassung im Chat.** Pro Schritt: `OK` / `FAIL` + je eine Zeile Evidenz
(ausgeblendete Werte!). Danach:
- **GRÜN** = Schritte 4–6 wie erwartet → LLM-Variante live in wger-web,
  Zurückschalten per Schritt 7.
- **ROT** = welcher Schritt, welche Beobachtung, was du NICHT weiter gemacht hast.

**b) Bericht als Datei im Repo**, der vorgesehene Rückkanal: `cf/berichte/README.md`
und `cf/berichte/VORLAGE.md` beschreiben Format und Pflichtfelder (Frontmatter,
sechs Abschnitte, anonymisiert: keine Hostnamen, Adressen, Tokens, Personen).
- Branch ab `cf-port`, z. B. `bericht/llm-spracherkennung`; nur die neue Datei
  `cf/berichte/2026-MM-TT-<typ>-llm-spracherkennung.md`, sonst nichts.
- GRÜN → `typ: messung` (die Shim-Doku steht auf „nicht gemessen, bitte prüfen"),
  mit Latenz je Aufruf aus Schritt 5/6 in „Messwerte".
  ROT → `typ: fehler`, `schwere: blockiert`.
- `schritt: 0` (außerhalb der Anleitung), `variante` und `detector` wie auf
  der Plattform gebaut (vermutlich `buildpack`/`lingua`, bitte ablesen),
  `plattform: tas`, `status: offen`.
- Kein Merge, kein Push nach `cf-port`; der Branch wird vom Entwickler gelesen.

Niemals ausführen: andere Apps anfassen, Manifest oder sonstige Repo-Dateien
ändern (einzige Ausnahme: die eine Berichtsdatei unter `cf/berichte/` auf dem
eigenen Branch), Build auslösen, <LLM_DIENST>-Parameter außerhalb der beiden Prompts
aus Schritt 5 ändern.

## Anhang: FW-Wunschtext (falls Schritt 3a timeout)

> **Betreff:** FW-Freigabe: PaaS-App (Org <CF_ORG>) → <LLM_DIENST> `<LLM_HOST>:443/TCP`
>
> Sehr geehrtes <PLATTFORMTEAM>,
>
> wir (<AUFTRAGGEBER_EINHEIT>) betreiben die App `wger-web` (Space `<CF_SPACE>`, Org `<CF_ORG>`,
> Foundation <FOUNDATION>, `<CF_API_HOST>`) und möchten für die
> Spracherkennung den internen LLM-Endpunkt **<LLM_DIENST>**
> (`<LLM_URL>`, OpenAI-kompatible vLLM-API,
> Modell `qwen3.8-27b`) aufrufen.
>
> **Anfrage:** Freigabe **ausgehend** von den Apps der Foundation **<FOUNDATION>**
> (bzw. des Spaces `<CF_SPACE>`) nach `<LLM_HOST>`, **TCP 443** (HTTPS).
>
> **Begründung / Abgrenzung:** Die App ruft ausschließlich
> `POST /v1/chat/completions` (und zu Diagnosezwecken `GET /v1/models`) auf;
> keine anderen Endpunkte. Kein Upload, kein anderer Datenabfluss. Der Endpunkt
> ist ein interner vLLM-Server (keyless im Demobetrieb). Alternative (lokales
> lingua-Modell, 170 MB im Droplet) bleibt aktiv zurückschaltbar.
>
> Gemessen 27.11.2026: aus dem App-Container `curl -k -m 20
> <LLM_URL>/models` → Connection timeout (20 s);
> von einer internen VDI ist derselbe Endpunkt erreichbar (HTTP 200).
>
> Mit freundlichen Grüßen
> <AUFTRAGGEBER>, <AUFTRAGGEBER_EMAIL>

## Anhang: was NICHT Teil dieses Auftrags ist
- Eigener `DETECTOR=llm`-Build (ohne lingua im Droplet, ~306 MB weniger) —
  spätere Optimierungsstufe, eigener Auftrag.
- OSB-Service-Broker statt user-provided Service — später, falls mehrere
  Konsumenten/Quotas/Key-Rotation kommen.
- `wger-worker`/`wger-beat` auf LLM umstellen.
- Änderungen an Repo, Manifest, CI oder an <LLM_DIENST> selbst (Ausnahme: die
  Berichtsdatei aus Schritt 8b auf eigenem Branch).
