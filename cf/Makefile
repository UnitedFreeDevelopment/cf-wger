# Betrieb von wger auf Cloud Foundry. Aufruf aus dem Wurzelverzeichnis:
#   make -f cf/Makefile <target>
# Reihenfolge beim ersten Mal: secrets, s3-dev (nur lokal), assets, push-web, init, images-import, push.
SHELL := /bin/bash
# CURDIR statt $(dir ...): make zerlegt Pfade mit Leerzeichen, und das
# Arbeitsverzeichnis hat eines. Deshalb der Aufruf aus dem Wurzelverzeichnis.
ROOT  := $(CURDIR)
# Welche Vars-Datei das Manifest bekommt: cnb (Paketo, Vorgabe, gemessen auf
# cfk8s) oder buildpack (klassischer python_buildpack, fuer Plattformen ohne
# Registry-Zugang). Begruendung in cf/manifest.yml.
VARIANT ?= cnb
# Spracherkennung: lingua (lokal, 170 MB Wheel, Vorgabe) oder llm (Text-LLM der
# Plattform ueber den Dienst wger-llm; lingua ist dann nicht installiert).
# Begruendung in CLAUDE.md "Spracherkennung". Entscheidet die Paketliste
# (requirements), ob das lingua-Wheel mitgeht (wheels) und die Variable
# language_detector im Manifest.
DETECTOR ?= lingua
LOCK_lingua = cf/requirements.lock.txt
LOCK_llm    = cf/requirements.llm.lock.txt
PUSH   = cf push -f cf/manifest.yml --vars-file cf/vars.$(VARIANT).yml --var language_detector=$(DETECTOR)

.PHONY: help export assets requirements wheels wheels-fetch vendor secrets s3-dev push-web push init images-fetch images-export images-import logs clean

help:
	@grep -E '^## ' $(lastword $(MAKEFILE_LIST)) | sed 's/^## /  /'

## export: uv.lock nach cf/requirements.lock.txt (mit gunicorn aus der Gruppe docker)
export:
	@# --no-emit-project: wger selbst wird nicht installiert, der App-Root liegt
	@# ohnehin auf dem sys.path. --group docker bringt gunicorn mit.
	cd "$(ROOT)" && uv export --no-hashes --no-dev --no-emit-project --group docker \
	  --format requirements-txt -o cf/requirements.lock.txt
	@# Dasselbe ohne lingua, fuer DETECTOR=llm; beide Dateien liegen im Repo.
	cd "$(ROOT)" && uv export --no-hashes --no-dev --no-emit-project --group docker \
	  --no-emit-package lingua-language-detector \
	  --format requirements-txt -o cf/requirements.llm.lock.txt

## requirements: cf/requirements.active.txt je DETECTOR schreiben (push ruft das auf)
requirements:
	@# requirements.txt im Wurzelverzeichnis verweist auf diese erzeugte Datei,
	@# weil der Buildpack nur die eine Datei liest und sie je Zielplattform
	@# verschieden sein muss. Nicht im Repo (.gitignore).
	@test -n "$(LOCK_$(DETECTOR))" || { echo "DETECTOR muss lingua oder llm sein, nicht '$(DETECTOR)'"; exit 1; }
	cd "$(ROOT)" && cp $(LOCK_$(DETECTOR)) cf/requirements.active.txt
	@echo "   DETECTOR=$(DETECTOR): $$(grep -c '==' cf/requirements.active.txt) Pakete"

## assets: node_modules/ und bootstrap-compiled.css vorbauen (vor jedem push)
assets:
	@# Wie extras/docker/production/Dockerfile von Upstream: nur die
	@# Produktionspakete (38 MB statt 428 MB mit Entwicklungspaketen), dazu
	@# @wger-project/react-components einzeln, weil es als devDependency
	@# gefuehrt wird, die Templates es aber zur Laufzeit laden. sass steht
	@# nicht in package.json; npx holt es.
	cd "$(ROOT)" && rm -rf node_modules && npm ci --omit=dev --no-audit --no-fund
	cd "$(ROOT)" && P="@wger-project/react-components" && \
	  V=$$(node -p "require('./package.json').devDependencies['$$P']") && \
	  T=$$(npm pack $$P@$$V 2>/dev/null | tail -1) && \
	  mkdir -p node_modules/$$P && tar -xzf $$T -C node_modules/$$P --strip-components=1 && rm -f $$T
	cd "$(ROOT)" && npx --yes sass --quiet wger/core/static/scss/main.scss wger/core/static/bootstrap-compiled.css
	@# collectstatic hier statt beim Staging: Paketo kennt keinen Django-Hook,
	@# und ohne Ausschluss waren es 418 MB (gemessen 2026-11-21) - weil
	@# fontawesomefree und die npm-Pakete komplett kopiert werden, obwohl die
	@# Templates nur fontawesomefree/css, webfonts und sieben node-Dateien
	@# laden. Verzeichnisnamen werden als Name geprueft, Dateien gegen ihren
	@# Pfad INNERHALB des jeweiligen Static-Verzeichnisses (node_modules/ ohne
	@# das Praefix "node/"). locales/ und muscles/ der react-components laedt
	@# der Browser zur Laufzeit - die bleiben.
	cd "$(ROOT)" && rm -rf staticfiles && VCAP_SERVICES='{}' VCAP_APPLICATION='{}' \
	  DJANGO_SETTINGS_MODULE=cf.settings uv run python manage.py collectstatic --noinput \
	  -i js-packages -i svgs -i metadata -i otfs -i sprites -i less -i scss -i assetTemplates \
	  -i src -i "*.map" -i "*.ts" -i "*.md" -i "LICENSE*" \
	  -i "fontawesomefree/js/*" \
	  -i "bootstrap/js/*" -i "bootstrap/dist/css/*" -i "@popperjs/core/lib/*" -i "datatables.net/types/*" \
	  2>&1 | grep -v "Can't find name" | tail -1
	@cd "$(ROOT)" && du -sh staticfiles node_modules | sed 's/^/   /'

## vendor: Wheels fuer den klassischen Buildpack nach vendor/ laden (nur VARIANT=buildpack)
vendor: requirements
	@# Fuer Plattformen, deren Staging PyPI nicht erreicht. Liegt vendor/ im
	@# Push, installiert der python_buildpack mit --no-index --find-links
	@# daraus (src/python/supply/supply.go, RunPipVendored) und laedt nichts
	@# nach. Geladen wird hier auf dem Entwicklungsrechner, deshalb muessen
	@# Plattform und Python-Version ausdruecklich die des Containers sein:
	@# cflinuxfs4 ist x86_64 mit glibc 2.35 (gemessen), also manylinux bis
	@# _2_34; CPython 3.13 wie in runtime.txt. --only-binary=:all: lehnt
	@# Quellpakete ab - die braeuchten beim Staging Build-Werkzeuge von PyPI.
	@# Fehlt ein Wheel, bricht der Lauf ab und nennt das Paket.
	cd "$(ROOT)" && rm -rf vendor && python3 -m pip download -q \
	  -r cf/requirements.active.txt -r cf/requirements-cf.txt -d vendor \
	  --only-binary=:all: --python-version 3.13 --implementation cp \
	  --abi cp313 --abi abi3 --abi none \
	  --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 \
	  --platform manylinux_2_28_x86_64 --platform manylinux_2_34_x86_64 \
	  --platform linux_x86_64
	@cd "$(ROOT)" && echo "   $$(ls vendor | wc -l) Wheels, $$(du -sh vendor | cut -f1)"

## wheels: cf/wheels/ fuer den Push herrichten: geteiltes Wheel zusammensetzen, Pruefsummen pruefen
wheels: requirements
	@# cf/wheels/ fuehrt Wheels, die der Index der Zielplattform nicht hat
	@# (psycopg-binary, lingua); requirements.txt zeigt mit --find-links
	@# dorthin, pip nimmt sie von dort und alles andere vom Index. Das
	@# lingua-Wheel hat 170 MB, GitHub nimmt keine Datei ueber 100 MB, Git LFS
	@# steht nicht zur Verfuegung: deshalb liegt es im Repo als Teile zu 45 MB
	@# (split), und hier wird es zusammengesetzt. .cfignore haelt die Teile aus
	@# dem Droplet, .gitignore das Ganze aus dem Repo. Die Pruefsumme ist die
	@# von PyPI (cf/wheels/SHA256SUMS); stimmt sie nicht, bricht der Lauf ab.
	@# Scheitert die Pruefung, kommt das Zusammengesetzte weg: sonst bliebe
	@# ein falsches Wheel liegen, und der naechste Lauf setzt nicht neu zusammen.
	@# Mit DETECTOR=llm bleibt das lingua-Wheel zu Hause: nur loeschen, nicht
	@# zusammensetzen, sonst ginge es mit dem App-Verzeichnis ins Droplet.
	cd "$(ROOT)/cf/wheels" && for p in *.whl.part-aa; do \
	  w="$${p%.part-aa}"; \
	  if [ "$(DETECTOR)" = llm ]; then rm -f "$$w"; else [ -f "$$w" ] || cat "$$w".part-* > "$$w"; fi; done \
	  && { sha256sum --check --quiet --ignore-missing SHA256SUMS || { rm -f $$(ls *.whl.part-aa | sed 's/\.part-aa$$//'); exit 1; }; } \
	  && echo "   cf/wheels (DETECTOR=$(DETECTOR)): $$(ls *.whl | wc -l) Wheels, Pruefsummen stimmen"

## wheels-fetch: die Wheels in cf/wheels/ von PyPI neu laden (nach einem Versionswechsel im Lockfile)
wheels-fetch:
	@# Versionen aus cf/requirements.lock.txt, Plattform wie bei vendor
	@# (cflinuxfs4: x86_64, glibc 2.35, CPython 3.13). Was groesser als 45 MB
	@# ist, wird geteilt; SHA256SUMS traegt die Summen der ganzen Wheels, zum
	@# Vergleich mit PyPI. Danach: git add cf/wheels, und `make wheels` als
	@# Gegenprobe.
	cd "$(ROOT)" && rm -rf cf/wheels && mkdir cf/wheels && python3 -m pip download -q --no-deps -d cf/wheels \
	  --only-binary=:all: --python-version 3.13 --implementation cp \
	  --abi cp313 --abi abi3 --abi none \
	  --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 \
	  --platform manylinux_2_28_x86_64 --platform manylinux_2_34_x86_64 \
	  --platform linux_x86_64 \
	  $$(grep -E '^(lingua-language-detector|psycopg-binary)==' cf/requirements.lock.txt | sed 's/ ;.*//')
	cd "$(ROOT)/cf/wheels" && sha256sum *.whl > SHA256SUMS && for w in *.whl; do \
	  if [ $$(stat -c %s "$$w") -gt $$((45*1024*1024)) ]; then \
	    split -b 45m --suffix-length=2 "$$w" "$$w.part-" && rm "$$w"; fi; done && ls -l

## secrets: benutzerdefinierten Dienst wger-secrets mit zufaelligem SECRET_KEY anlegen
secrets:
	@# Der Schluessel wird nirgends ausgegeben. Existiert der Dienst schon,
	@# bleibt er - ein neuer Schluessel wuerde alle Sessions ungueltig machen.
	@if cf service wger-secrets >/dev/null 2>&1; then echo "   wger-secrets vorhanden"; else \
	  cf create-user-provided-service wger-secrets \
	    -p "$$(python3 -c 'import json,secrets; print(json.dumps({"secret_key": secrets.token_urlsafe(64)}))')"; fi

## s3-dev: versitygw (S3) als CF-App, Bucket und Dienst wger-s3 anlegen (nur lokale Plattform, die kein S3 hat)
S3_DEV = cf/dev/.s3-dev.json
s3-dev:
	@# Zugangsdaten einmal erzeugen und lokal behalten (.gitignore): ein
	@# zweiter Lauf nimmt dieselben, sonst passen Dienst und versitygw nicht mehr
	@# zusammen. Der Endpunkt ist die Route der App auf der Apps-Domaene der
	@# Plattform; dieselbe Adresse gilt fuer die App und fuer den Browser.
	@test -f $(S3_DEV) || { d=$$(cf domains | awk 'NR>3 && $$2=="shared" && $$3!="true"{print $$1; exit}'); \
	  python3 -c "import json,secrets; json.dump({'endpoint': 'http://wger-s3-dev.$$d', 'bucket': 'wger-media', \
	    'access_key_id': secrets.token_hex(8), 'secret_access_key': secrets.token_urlsafe(24)}, open('$(S3_DEV)','w'), indent=1)"; }
	cd "$(ROOT)" && cf push -f cf/dev/versitygw.yml \
	  --var access_key=$$(python3 -c "import json;print(json.load(open('$(S3_DEV)'))['access_key_id'])") \
	  --var secret_key=$$(python3 -c "import json;print(json.load(open('$(S3_DEV)'))['secret_access_key'])")
	@# --no-project: boto3 soll nicht in die Projektumgebung, es ist nur hier noetig.
	cd "$(ROOT)" && uv run --no-project --with boto3 python cf/dev/s3_bucket.py $(S3_DEV)
	@# Tag s3, weil cf/settings.py die Bindung ueber Tag oder Namen findet.
	@if cf service wger-s3 >/dev/null 2>&1; then cf update-user-provided-service wger-s3 -p $(S3_DEV) -t s3; \
	  else cf create-user-provided-service wger-s3 -p $(S3_DEV) -t s3; fi

## push-web: nur wger-web (erster Push, vor init)
push-web: wheels
	cd "$(ROOT)" && $(PUSH) wger-web

## push: alle drei Apps, nacheinander
push: wheels
	@# Nacheinander statt `cf push -f cf/manifest.yml` in einem Zug: der staged
	@# alle drei parallel, und Beat lief dabei in den Staging-Timeout der
	@# Plattform (15 Minuten; gemessen 2026-11-21). Allein braucht jede App mit
	@# dem Build-Cache der vorigen rund drei Minuten.
	cd "$(ROOT)" && for app in wger-web wger-worker wger-beat; do $(PUSH) $$app || exit 1; done

## init: Migrationen, Fixtures, Admin, Cache-Tabelle, Site-URL - als Task, nicht beim Start
init:
	@# `wger bootstrap` migriert, laedt die Fixtures und legt admin/adminadmin
	@# an, wenn die Datenbank leer ist - Passwort danach aendern.
	@# createcachetable: der Cache liegt ohne Redis in der Datenbank (cf/settings.py).
	@# -m/-k ausdruecklich: mit dem Standard (1G/1G) starb die Migration
	@# nutrition.0014 mit Exit 137 (gemessen 2026-11-21), und 1G Platte ist
	@# kleiner als das Droplet (1,5G). Mehr als 2G Platte laesst die Plattform nicht zu.
	cf run-task wger-web --name init --wait -m 2G -k 2G \
	  --command "python -m wger bootstrap --no-process-static && python manage.py createcachetable && python manage.py set-site-url"

## images-fetch: Uebungsbilder von wger.de in Storage und Datenbank laden (braucht ausgehendes Internet)
images-fetch:
	@# Upstream-Befehl; schreibt ueber den Default-Storage, auf CF also nach
	@# S3. Ohne S3-Bindung landen die Dateien im fluechtigen Dateisystem des
	@# Task-Containers und sind mit dessen Ende weg - nur die Datenbank-
	@# eintraege blieben. Deshalb vorher s3-dev bzw. die S3-Bindung.
	cf run-task wger-web --name images-fetch --wait -m 1G -k 2G \
	  --command "python manage.py download-exercise-images"

## images-export: Bilder und Datenbankeintraege aus der Instanz nach cf/exercise-images/ (fuer Plattformen ohne Internet)
images-export:
	@# Ueber SSH statt als Task: ein Task gibt nichts zurueck. -T: kein
	@# Terminal, sonst ist der tar-Strom nicht binaer-sauber. appenv.sh gibt
	@# der Sitzung Python-Umgebung und Arbeitsverzeichnis des laufenden
	@# Prozesses; gefunden wird es ueber dessen Arbeitsverzeichnis, weil das
	@# je Bauweise anders heisst (~/workspace bei cnb, ~/app beim Buildpack).
	cd "$(ROOT)" && rm -rf cf/exercise-images && mkdir -p cf/exercise-images && \
	  cf ssh -T wger-web -c 'cd $$(readlink /proc/$$(pgrep -o -f gunicorn)/cwd) && cf/appenv.sh python cf/exercise_images.py export -' \
	  | tar -x -C cf/exercise-images
	@cd "$(ROOT)" && echo "   $$(find cf/exercise-images/files -type f | wc -l) Dateien, $$(du -sh cf/exercise-images | cut -f1)"

## images-import: cf/exercise-images/ in Storage und Datenbank der Instanz laden (idempotent)
images-import:
	@# Das Verzeichnis geht mit dem Push ins Droplet; der Task liest es von
	@# dort. 1G reicht: das Skript haelt je ein Bild im Speicher.
	cf run-task wger-web --name images-import --wait -m 1G -k 2G \
	  --command "python cf/exercise_images.py import cf/exercise-images"

## logs: die letzten Zeilen von wger-web
logs:
	cf logs wger-web --recent | tail -50

## clean: Bauartefakte entfernen
clean:
	cd "$(ROOT)" && rm -rf node_modules staticfiles vendor cf/requirements.active.txt cf/wheels/lingua_language_detector-*.whl wger/core/static/bootstrap-compiled.css wger/core/static/bootstrap-compiled.css.map
