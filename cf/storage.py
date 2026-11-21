# Statische Dateien auf Cloud Foundry: whitenoise liefert sie aus dem Droplet
# aus, es gibt weder Nginx noch Object Storage davor.
#
# Warum nicht whitenoise.storage.CompressedManifestStaticFilesStorage direkt:
# Einige npm-Pakete unter node_modules/ verweisen aus CSS auf Dateien, die im
# Paket nicht liegen (Source Maps). Der Manifest-Storage von Django bricht
# collectstatic daran ab. Upstream loest das in
# wger.core.storage.LenientManifestStaticFilesStorage - diese Klasse haengt
# die Nachsicht vor die Kompression, mehr nicht.
from whitenoise.storage import CompressedManifestStaticFilesStorage

from wger.core.storage import LenientManifestStaticFilesStorage


class LenientCompressedManifestStaticFilesStorage(
    LenientManifestStaticFilesStorage,
    CompressedManifestStaticFilesStorage,
):
    """Manifest + gzip/brotli, aber fehlende Querverweise sind kein Fehler."""
