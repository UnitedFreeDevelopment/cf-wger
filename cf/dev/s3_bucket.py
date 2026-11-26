"""Bucket im Entwicklungs-S3 (versitygw) anlegen, falls er fehlt.

Aufruf (vom Makefile, Target s3-dev):
    uv run --no-project --with boto3 python cf/dev/s3_bucket.py cf/dev/.s3-dev.json

Die JSON-Datei hat dieselben Schluessel wie der Dienst wger-s3
(cf/settings.py, Abschnitt S3): endpoint, bucket, access_key_id,
secret_access_key. versitygw legt Buckets nicht von selbst an, und die App soll
beim ersten Upload nicht an einem fehlenden Bucket scheitern.
"""

import json
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

cfg = json.load(open(sys.argv[1]))
s3 = boto3.client(
    's3',
    endpoint_url=cfg['endpoint'],
    aws_access_key_id=cfg['access_key_id'],
    aws_secret_access_key=cfg['secret_access_key'],
    region_name='us-east-1',
    # Pfad-Adressierung wie in cf/settings.py: virtuelle Hosts
    # (bucket.host) kann die CF-Route nicht aufloesen.
    config=Config(s3={'addressing_style': 'path'}, signature_version='s3v4'),
)
try:
    s3.head_bucket(Bucket=cfg['bucket'])
    print(f'   Bucket {cfg["bucket"]} vorhanden')
except ClientError:
    s3.create_bucket(Bucket=cfg['bucket'])
    print(f'   Bucket {cfg["bucket"]} angelegt')
