"""
Settings-Overlay fuer Cloud Foundry.

Upstream konfiguriert settings/main.py vollstaendig ueber Umgebungsvariablen.
Dieses Modul erfindet keine zweite Konfiguration, sondern uebersetzt die
Service-Bindings aus VCAP_SERVICES in genau die Variablen, die main.py liest,
und importiert main.py danach. Ueberschrieben wird nur, was main.py nicht
ausdruecken kann (Cache ohne Redis, whitenoise, Pfade im Droplet).

Aktiv ueber DJANGO_SETTINGS_MODULE=cf.settings (siehe cf/manifest.yml).
Gilt fuer web, worker, beat und fuer collectstatic beim Staging - dort gibt es
VCAP_SERVICES ebenfalls, aber keine Datenbankverbindung.
"""

import json
import os
from urllib.parse import urlparse

# ---------------------------------------------------------------- Bindings


def _vcap(name):
    try:
        return json.loads(os.environ.get(name, '{}'))
    except ValueError:
        return {}


def _bindings():
    """Alle Bindings als (Angebot, Binding), ueber alle Angebote hinweg."""
    for offering, items in _vcap('VCAP_SERVICES').items():
        for binding in items:
            yield offering, binding


def _binding(tags=(), names=()):
    """
    Erstes Binding, dessen Tags oder Angebotsname passen.

    Tags sind die verlaesslichere Spur: der Broker vergibt sie je Angebot
    (cnpg-postgresql traegt "postgresql", rabbitmq-cluster traegt "amqp").
    Der Name faengt benutzerdefinierte Dienste (cf cups) ohne Tags.
    """
    for offering, binding in _bindings():
        binding_tags = {t.lower() for t in binding.get('tags', [])}
        label = (binding.get('label') or offering or '').lower()
        name = (binding.get('name') or '').lower()
        if binding_tags & set(tags) or name in names or label in names:
            return binding.get('credentials', {})
    return None


def _setdefault(key, value):
    """Nur setzen, wenn der Betreiber die Variable nicht selbst gesetzt hat."""
    if value is not None and value != '':
        os.environ.setdefault(key, str(value))


# ---------------------------------------------------------------- Datenbank
# Die CNPG-Bindung traegt "host" als Kurznamen des Kubernetes-Service ohne
# Namespace; aus einem CF-Container ist der nicht aufloesbar (gemessen mit
# samples/db-probe der Plattform). Verlaesslich ist der Hostname aus fqdn-uri.
_db = _binding(tags=('postgresql', 'postgres'), names=('wger-db',))
if _db:
    _uri = urlparse(_db.get('fqdn-uri') or _db.get('uri') or '')
    _setdefault('DJANGO_DB_ENGINE', 'django.db.backends.postgresql')
    _setdefault('DJANGO_DB_DATABASE', _db.get('dbname') or _uri.path.lstrip('/'))
    _setdefault('DJANGO_DB_USER', _db.get('username') or _db.get('user') or _uri.username)
    _setdefault('DJANGO_DB_PASSWORD', _db.get('password') or _uri.password)
    _setdefault('DJANGO_DB_HOST', _uri.hostname or _db.get('host'))
    _setdefault('DJANGO_DB_PORT', _uri.port or _db.get('port') or 5432)
else:
    # main.py verlangt Engine und Name ohne Default und bricht sonst schon
    # beim Import ab - auch bei collectstatic, das gar keine Datenbank braucht.
    _setdefault('DJANGO_DB_ENGINE', 'django.db.backends.postgresql')
    _setdefault('DJANGO_DB_DATABASE', 'wger')

# ---------------------------------------------------------------- Redis
# Sessions (cached_db) und die Login-Sperren von django-axes liegen im Cache.
# Mit Redis-Bindung geht beides dorthin, und Celery nimmt Redis als Broker,
# solange kein eigener Broker gebunden ist.
_redis = _binding(tags=('redis', 'valkey'), names=('wger-redis', 'wger-cache'))
_redis_url = _redis and (_redis.get('uri') or _redis.get('url'))
if _redis_url:
    _setdefault('DJANGO_CACHE_BACKEND', 'django_redis.cache.RedisCache')
    _setdefault('DJANGO_CACHE_LOCATION', _redis_url)
    _setdefault('DJANGO_CACHE_CLIENT_CLASS', 'django_redis.client.DefaultClient')
    _setdefault('CELERY_BROKER', _redis_url)
    _setdefault('CELERY_BACKEND', _redis_url)

# ---------------------------------------------------------------- Celery
# Auf der lokalen Plattform gibt es kein Redis, aber RabbitMQ. Celery kann
# AMQP nativ; ein Ergebnis-Backend braucht wger nicht, rpc:// laeuft ueber
# denselben Broker. Die Variablen heissen bei Upstream CELERY_BROKER und
# CELERY_BACKEND, nicht wie die Django-Settings.
_amqp = _binding(tags=('amqp', 'rabbitmq'), names=('wger-mq',))
if _amqp and _amqp.get('uri'):
    _setdefault('CELERY_BROKER', _amqp['uri'])
    _setdefault('CELERY_BACKEND', 'rpc://')
if os.environ.get('CELERY_BROKER'):
    # Schaltet unter anderem den Mailversand auf den Worker um - der muss
    # dann auch laufen (cf/manifest.yml: wger-worker).
    _setdefault('USE_CELERY', 'True')

# ---------------------------------------------------------------- S3
# Das CF-Dateisystem ist fluechtig; Uploads und die Uebungsbilder gehoeren in
# einen Object Storage. Gemessen 2026-11-26 gegen versitygw (S3-Gateway) als CF-App
# (cf/dev/versitygw.yml): Upload ueber download-exercise-images und
# cf/exercise_images.py, Auslieferung an den Browser ueber signierte URLs.
# Gegen das S3 der Zielplattform nicht gemessen; die Schluesselnamen der
# Bindung sind die des benutzerdefinierten Dienstes wger-s3 (cf/README.md),
# fuer einen Marktplatz-Dienst stehen hier Alternativen, BITTE PRUEFEN.
_s3 = _binding(tags=('s3', 'object-storage', 'minio'), names=('wger-s3',))
if _s3:
    _endpoint = _s3.get('endpoint') or _s3.get('endpoint_url') or _s3.get('url') or ''
    _setdefault('USE_S3_MEDIA_FILES', 'True')
    _setdefault('AWS_ACCESS_KEY_ID', _s3.get('access_key_id') or _s3.get('access_key') or _s3.get('accessKey'))
    _setdefault('AWS_SECRET_ACCESS_KEY', _s3.get('secret_access_key') or _s3.get('secret_key') or _s3.get('secretKey'))
    _setdefault('AWS_STORAGE_BUCKET_NAME', _s3.get('bucket') or _s3.get('bucket_name'))
    _setdefault('AWS_S3_REGION_NAME', _s3.get('region') or 'us-east-1')
    _setdefault('AWS_S3_DOMAIN', urlparse(_endpoint).hostname or '')
    _setdefault('AWS_S3_ENDPOINT_URL', _endpoint)
    # Der zweite Teil steht unten, nach dem Import von main.py.

# ---------------------------------------------------------------- Geheimnisse
# Kein SECRET_KEY im Manifest oder Repo: er kommt aus einem benutzer-
# definierten Dienst (cf cups wger-secrets -p '{"secret_key": "..."}').
# Fehlt er, erzeugt main.py einen Zufallsschluessel und warnt - Sessions
# ueberleben dann keinen Neustart.
_secrets = _binding(names=('wger-secrets',))
if _secrets:
    _setdefault('SECRET_KEY', _secrets.get('secret_key'))
    _setdefault('JWT_PUBLIC_KEY', _secrets.get('jwt_public_key'))
    _setdefault('JWT_PRIVATE_KEY', _secrets.get('jwt_private_key'))
    _setdefault('EMAIL_HOST_USER', _secrets.get('email_host_user'))
    _setdefault('EMAIL_HOST_PASSWORD', _secrets.get('email_host_password'))

# ---------------------------------------------------------------- Spracherkennung
# Upstream prueft die Sprache von Uebungstexten mit lingua (170 MB Wheel,
# 306 MB im Droplet). Mit WGER_LANGUAGE_DETECTOR=llm (cf/manifest.yml, Variable
# language_detector, Makefile DETECTOR=llm) ist lingua nicht installiert
# (cf/requirements.llm.lock.txt); stattdessen liegt cf/shim vor den
# site-packages, und `import lingua` in den zwei Upstream-Dateien trifft den
# Shim, der ein Text-LLM der Plattform fragt. Der Endpunkt kommt aus dem
# benutzerdefinierten Dienst wger-llm (url, api_key, model). Begruendung und
# Grenzen: CLAUDE.md "Spracherkennung", cf/shim/lingua/__init__.py.
import sys  # noqa: E402

if os.environ.get('WGER_LANGUAGE_DETECTOR', 'lingua') == 'llm':
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shim'))
    _llm = _binding(tags=('llm', 'openai'), names=('wger-llm',))
    if _llm:
        _setdefault('WGER_LLM_URL', _llm.get('url') or _llm.get('base_url') or _llm.get('uri'))
        _setdefault('WGER_LLM_API_KEY', _llm.get('api_key') or _llm.get('token'))
        _setdefault('WGER_LLM_MODEL', _llm.get('model'))

# ---------------------------------------------------------------- Route
# Die Route kennt nur die Plattform. Hinter dem Gorouter kommt jede Anfrage
# als HTTP an, das Protokoll steht in X-Forwarded-Proto; ohne diese
# Einstellung haelt Django alles fuer unverschluesselt und CSRF schlaegt fehl.
_app = _vcap('VCAP_APPLICATION')
_uris = _app.get('application_uris') or []
# Ob die Route per HTTPS erreichbar ist, entscheidet die Plattform. Auf der
# lokalen Plattform ist es HTTP (WGER_SITE_SCHEME im Manifest).
_scheme = os.environ.get('WGER_SITE_SCHEME', 'https')
if _uris:
    _setdefault('SITE_URL', f'{_scheme}://{_uris[0]}')
    _setdefault('CSRF_TRUSTED_ORIGINS', ','.join(f'{s}://{u}' for u in _uris for s in ('https', 'http')))
_setdefault('X_FORWARDED_PROTO_HEADER_SET', 'True')
_setdefault('USE_X_FORWARDED_HOST', 'True')
# Der Gorouter haengt die Client-Adresse an X-Forwarded-For; sonst sieht
# django-axes nur den Router und sperrt alle Nutzer gemeinsam.
_setdefault('AXES_IPWARE_META_PRECEDENCE_ORDER', 'HTTP_X_FORWARDED_FOR')
_setdefault('AXES_IPWARE_PROXY_COUNT', '1')

# ---------------------------------------------------------------- Pfade
# Alles im Droplet, nicht unter /home/wger wie im Docker-Image. staticfiles/
# fuellt der Buildpack beim Staging (collectstatic), whitenoise liest daraus.
# media/ ist fluechtig - ohne S3-Bindung gehen Uploads beim Neustart verloren.
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_setdefault('DJANGO_STATIC_ROOT', os.path.join(_root, 'staticfiles'))
_setdefault('DJANGO_MEDIA_ROOT', os.path.join(_root, 'media'))
_setdefault('DJANGO_STORAGES_STATICFILES_BACKEND', 'cf.storage.LenientCompressedManifestStaticFilesStorage')

# ---------------------------------------------------------------- Upstream
from settings.main import *  # noqa: E402, F403

# whitenoise so weit vorn wie moeglich, wie dessen Dokumentation es verlangt.
# Upstream fuehrt keine SecurityMiddleware; an erster Stelle steht der
# Prometheus-Zaehler, und der soll statische Anfragen weiter mitzaehlen.
_prometheus = 'django_prometheus.middleware.PrometheusBeforeMiddleware'
_pos = MIDDLEWARE.index(_prometheus) + 1 if _prometheus in MIDDLEWARE else 0  # noqa: F405
MIDDLEWARE.insert(_pos, 'whitenoise.middleware.WhiteNoiseMiddleware')  # noqa: F405

# Ohne Redis bleibt main.py beim LocMem-Cache - je Prozess getrennt. Damit
# waeren Sessions und Login-Sperren bei zwei Gunicorn-Workern inkonsistent.
# Die Datenbank ist der einzige gemeinsame Speicher, den jede Instanz hat.
# Tabelle anlegen: python manage.py createcachetable (Teil von `make init`).
if not os.environ.get('DJANGO_CACHE_BACKEND'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'wger_cache',
            'TIMEOUT': 30 * 24 * 60 * 60,
        }
    }

# ---------------------------------------------------------------- S3, Teil 2
# main.py nimmt AWS an: Dateien liegen unter bucket.region.domain, der Browser
# liest sie dort ohne Signatur, der Bucket ist also anonym lesbar. Ein
# S3-kompatibler Dienst einer Plattform hat weder diese Namensform noch einen
# anonymen Bucket. Deshalb:
# - Pfad-Adressierung (endpoint/bucket/schluessel): eine CF-Route kann
#   bucket.host nicht aufloesen; versitygw, MinIO und die meisten Dienste koennen Pfade.
# - signierte URLs: der Browser liest direkt vom Endpunkt, mit den Rechten
#   der App und befristet (AWS_QUERYSTRING_EXPIRE, Vorgabe 3600 s). Der
#   Endpunkt muss dafuer vom Browser erreichbar sein, nicht nur von der App.
# Traegt die Bindung `public_url` (Adresse bis einschliesslich Bucket, z. B.
# https://s3.example/wger-media), liest der Browser unsigniert von dort - der
# Bucket muss dann anonym lesbar sein. Das ist der Weg, wenn der Endpunkt
# vom Browser aus nicht erreichbar ist, wohl aber ein CDN oder Proxy davor.
# Gemessen: signierte URLs am versitygw (cf/README.md "Uebungsbilder");
# der Weg ueber public_url nicht, BITTE PRUEFEN.
if _s3:
    AWS_S3_ADDRESSING_STYLE = _s3.get('addressing_style') or 'path'
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    _location = STORAGES['default']['OPTIONS']['location']  # noqa: F405
    _public = _s3.get('public_url')
    if _public:
        _p = urlparse(_public)
        AWS_S3_URL_PROTOCOL = f'{_p.scheme}:'
        AWS_S3_CUSTOM_DOMAIN = f'{_p.netloc}{_p.path.rstrip("/")}'
        AWS_QUERYSTRING_AUTH = False
        MEDIA_URL = f'{_public.rstrip("/")}/{_location}/'
    else:
        AWS_S3_CUSTOM_DOMAIN = None
        AWS_QUERYSTRING_AUTH = True
        MEDIA_URL = f'{AWS_S3_ENDPOINT_URL.rstrip("/")}/{AWS_STORAGE_BUCKET_NAME}/{_location}/'  # noqa: F405
