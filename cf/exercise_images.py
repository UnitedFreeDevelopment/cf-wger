"""Uebungsbilder zwischen einer wger-Instanz und einem Verzeichnis bewegen.

    python cf/exercise_images.py export DIR|-
    python cf/exercise_images.py import DIR

Warum das Skript existiert: Upstream holt Uebungsbilder mit
`download-exercise-images` von wger.de. Auf der Zielplattform gibt es keinen
Weg dorthin, also muessen die Bilder mit dem Push kommen - als Dateien UND
als Datenbankeintraege (exercises.ExerciseImage), denn erst der Eintrag
verbindet Bild und Uebung. `export` schreibt beides aus einer Instanz, die
den Download machen konnte, `import` liest es in eine Instanz ein, die es
nicht kann. Die Dateien landen im Media-Storage der Instanz, auf CF also in
S3 (cf/settings.py).

Format von DIR: images.json (Liste) und files/<pfad im storage>. Uebungen
werden ueber ihre UUID zugeordnet, nicht ueber die numerische ID: die UUID
ist bei Upstream das instanzuebergreifende Kennzeichen, die ID nicht.
Bilder ebenso. Darum ist `import` idempotent und laeuft auch gegen eine
Datenbank, deren Uebungs-IDs anders vergeben sind.

`export -` schreibt ein tar nach stdout, fuer `cf ssh -T` (cf/Makefile,
images-export): ein Task kann nichts zurueckgeben, eine SSH-Sitzung schon.

Kein Management-Command, weil cf/ keine Django-App ist und Upstream-Code
nicht angefasst wird.
"""

import io
import json
import os
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cf.settings')

import django  # noqa: E402

django.setup()

from django.core.files.base import ContentFile  # noqa: E402

from wger.exercises.models import (  # noqa: E402
    Exercise,
    ExerciseImage,
)

FIELDS = (
    'is_main',
    'is_ai_generated',
    'style',
    'license_id',
    'license_title',
    'license_object_url',
    'license_author',
    'license_author_url',
    'license_derivative_source_url',
)


def export(target):
    images = ExerciseImage.objects.select_related('exercise').order_by('exercise_id', 'uuid')
    records = []
    files = []
    for img in images:
        rec = {f: getattr(img, f) for f in FIELDS}
        rec['uuid'] = str(img.uuid)
        rec['exercise_uuid'] = str(img.exercise.uuid)
        rec['file'] = img.image.name
        records.append(rec)
        with img.image.open('rb') as fh:
            files.append((img.image.name, fh.read()))
    meta = json.dumps(records, indent=1, sort_keys=True).encode()

    if target == '-':
        with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as tar:
            _add(tar, 'images.json', meta)
            for name, data in files:
                _add(tar, f'files/{name}', data)
    else:
        os.makedirs(target, exist_ok=True)
        with open(os.path.join(target, 'images.json'), 'wb') as fh:
            fh.write(meta)
        for name, data in files:
            path = os.path.join(target, 'files', name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as fh:
                fh.write(data)
    print(f'   {len(records)} Bilder exportiert', file=sys.stderr)


def _add(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def import_(source):
    with open(os.path.join(source, 'images.json')) as fh:
        records = json.load(fh)
    done = skipped = 0
    for rec in records:
        exercise = Exercise.objects.filter(uuid=rec['exercise_uuid']).first()
        if exercise is None:
            print(f'   Uebung {rec["exercise_uuid"]} fehlt, Bild {rec["uuid"]} uebersprungen')
            skipped += 1
            continue
        img = ExerciseImage.objects.filter(uuid=rec['uuid']).first() or ExerciseImage(uuid=rec['uuid'])
        img.exercise = exercise
        for f in FIELDS:
            setattr(img, f, rec[f])
        with open(os.path.join(source, 'files', rec['file']), 'rb') as fh:
            data = fh.read()
        # ImageField.save legt die Datei im Storage ab (Pfad aus upload_to:
        # exercise-images/<uebung>/<uuid>.<ext>) und speichert den Eintrag;
        # save() des Modells sorgt dabei fuer genau ein Hauptbild je Uebung.
        img.image.save(os.path.basename(rec['file']), ContentFile(data), save=True)
        done += 1
    print(f'   {done} Bilder importiert, {skipped} uebersprungen')


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('export', 'import'):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    (export if sys.argv[1] == 'export' else import_)(sys.argv[2])
