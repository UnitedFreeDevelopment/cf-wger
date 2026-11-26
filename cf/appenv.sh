#!/bin/sh
# Einen Befehl mit Umgebung und Arbeitsverzeichnis des laufenden App-Prozesses
# ausfuehren.
#
# `cf ssh` bringt VCAP_SERVICES und die Variablen aus dem Manifest mit, aber
# nicht, was der Buildpack dem Startbefehl mitgibt: PATH, PYTHONPATH und
# LD_LIBRARY_PATH zeigen auf die Layer von CPython und den Paketen. Ohne sie
# gibt es in der SSH-Sitzung kein `python` (gemessen 2026-11-26, Paketo).
# Auch das App-Verzeichnis haengt von der Bauweise ab: ~/workspace bei cnb,
# ~/app beim klassischen Buildpack. Der laufende Prozess hat beides; von
# dort wird es uebernommen, ohne etwas ueber Pfade anzunehmen.
#
# Aufruf (cf/Makefile, images-export):
#   cf ssh -T wger-web -c "$(readlink /proc/$(pgrep -o -f gunicorn)/cwd)/cf/appenv.sh python ..."
pid=$(pgrep -o -f gunicorn || pgrep -o -f celery)
if [ -z "$pid" ]; then
  echo "appenv.sh: kein App-Prozess (gunicorn/celery) gefunden" >&2
  exit 1
fi
for v in PATH PYTHONPATH LD_LIBRARY_PATH; do
  val=$(tr '\0' '\n' < "/proc/$pid/environ" | grep "^$v=" | cut -d= -f2-)
  [ -n "$val" ] && export "$v=$val"
done
cd "$(readlink "/proc/$pid/cwd")" || exit 1
exec "$@"
