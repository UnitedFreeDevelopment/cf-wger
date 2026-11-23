# Betrieb von wger auf Cloud Foundry. Aufruf aus dem Wurzelverzeichnis:
#   make -f cf/Makefile <target>
# Reihenfolge beim ersten Mal: secrets, assets, push-web, init, push.
SHELL := /bin/bash
# CURDIR statt $(dir ...): make zerlegt Pfade mit Leerzeichen, und das
# Arbeitsverzeichnis hat eines. Deshalb der Aufruf aus dem Wurzelverzeichnis.
ROOT  := $(CURDIR)
# Welche Vars-Datei das Manifest bekommt: cnb (Paketo, Vorgabe, gemessen auf
# cfk8s) oder buildpack (klassischer python_buildpack, fuer Plattformen ohne
# Registry-Zugang). Begruendung in cf/manifest.yml.
VARIANT ?= cnb
PUSH   = cf push -f cf/manifest.yml --vars-file cf/vars.$(VARIANT).yml

.PHONY: help export assets wheels wheels-fetch vendor secrets push-web push init logs clean

help:
	@grep -E '^## ' $(lastword $(MAKEFILE_LIST)) | sed 's/^## /  /'

## export: uv.lock nach cf/requirements.lock.txt (mit gunicorn aus der Gruppe docker)
export:
	@# --no-emit-project: wger selbst wird nicht installiert, der App-Root liegt
	@# ohnehin auf dem sys.path. --group docker bringt gunicorn mit.
	cd "$(ROOT)" && uv export --no-hashes --no-dev --no-emit-project --group docker \
	  --format requirements-txt -o cf/requirements.lock.txt

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
vendor:
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
	  -r cf/requirements.lock.txt -r cf/requirements-cf.txt -d vendor \
	  --only-binary=:all: --python-version 3.13 --implementation cp \
	  --abi cp313 --abi abi3 --abi none \
	  --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 \
	  --platform manylinux_2_28_x86_64 --platform manylinux_2_34_x86_64 \
	  --platform linux_x86_64
	@cd "$(ROOT)" && echo "   $$(ls vendor | wc -l) Wheels, $$(du -sh vendor | cut -f1)"

## wheels: cf/wheels/ fuer den Push herrichten: geteiltes Wheel zusammensetzen, Pruefsummen pruefen
wheels:
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
	cd "$(ROOT)/cf/wheels" && for p in *.whl.part-aa; do \
	  w="$${p%.part-aa}"; [ -f "$$w" ] || cat "$$w".part-* > "$$w"; done \
	  && { sha256sum --check --quiet SHA256SUMS || { rm -f $$(ls *.whl.part-aa | sed 's/\.part-aa$$//'); exit 1; }; } \
	  && echo "   cf/wheels: $$(ls *.whl | wc -l) Wheels, Pruefsummen stimmen"

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

## logs: die letzten Zeilen von wger-web
logs:
	cf logs wger-web --recent | tail -50

## clean: Bauartefakte entfernen
clean:
	cd "$(ROOT)" && rm -rf node_modules staticfiles vendor cf/wheels/lingua_language_detector-*.whl wger/core/static/bootstrap-compiled.css wger/core/static/bootstrap-compiled.css.map
