# Betrieb von wger auf Cloud Foundry. Aufruf aus dem Wurzelverzeichnis:
#   make -f cf/Makefile <target>
# Reihenfolge beim ersten Mal: secrets, assets, push-web, init, push.
SHELL := /bin/bash
# CURDIR statt $(dir ...): make zerlegt Pfade mit Leerzeichen, und das
# Arbeitsverzeichnis hat eines. Deshalb der Aufruf aus dem Wurzelverzeichnis.
ROOT  := $(CURDIR)

.PHONY: help export assets secrets push-web push init logs clean

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

## secrets: benutzerdefinierten Dienst wger-secrets mit zufaelligem SECRET_KEY anlegen
secrets:
	@# Der Schluessel wird nirgends ausgegeben. Existiert der Dienst schon,
	@# bleibt er - ein neuer Schluessel wuerde alle Sessions ungueltig machen.
	@if cf service wger-secrets >/dev/null 2>&1; then echo "   wger-secrets vorhanden"; else \
	  cf create-user-provided-service wger-secrets \
	    -p "$$(python3 -c 'import json,secrets; print(json.dumps({"secret_key": secrets.token_urlsafe(64)}))')"; fi

## push-web: nur wger-web (erster Push, vor init)
push-web:
	cd "$(ROOT)" && cf push wger-web -f cf/manifest.yml

## push: alle drei Apps
push:
	cd "$(ROOT)" && cf push -f cf/manifest.yml

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
	cd "$(ROOT)" && rm -rf node_modules staticfiles wger/core/static/bootstrap-compiled.css wger/core/static/bootstrap-compiled.css.map
