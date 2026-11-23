"""
Ersatz fuer das Paket `lingua` (lingua-language-detector), der die Sprache
eines Textes ueber ein LLM der Plattform bestimmt statt mit den lokalen
Modellen.

Warum: lingua kostet 170 MB als Wheel und 306 MB im Droplet (CLAUDE.md,
"Spracherkennung"). Auf einer Plattform, die ein Text-LLM als Dienst anbietet,
ist das vermeidbar. Upstream importiert lingua an zwei Stellen
(wger/exercises/api/validators.py, wger/core/api/serializers.py) und benutzt
genau: LanguageDetectorBuilder.from_all_languages().build(),
detect_language_of(text) -> Language | None mit .name und .iso_code_639_1.name,
compute_language_confidence_values(text). Mehr stellt dieses Modul nicht
nach. Es wird nur sichtbar, wenn cf/settings.py cf/shim vor die
site-packages setzt (WGER_LANGUAGE_DETECTOR=llm); sonst gilt das echte lingua.

Angenommen ist eine OpenAI-kompatible Chat-Schnittstelle
(POST {WGER_LLM_URL}/chat/completions, Bearer-Token). Gegen den Endpunkt der
Zielplattform ist das nicht gemessen, nur gegen einen Stub - BITTE PRUEFEN,
sobald die Bindung existiert (cf/README.md, "Spracherkennung ueber ein LLM").
"""

import logging
import os
import re
from dataclasses import dataclass

import requests


logger = logging.getLogger(__name__)

# Englische Namen wie bei lingua (Language.GERMAN.name == 'GERMAN'); Upstream
# zeigt .name.capitalize() in der Fehlermeldung. Die Liste deckt die Sprachen
# aus wger/core/fixtures/languages.json; fuer andere Codes steht der Code.
_NAMES = {
    'ar': 'ARABIC', 'az': 'AZERBAIJANI', 'bg': 'BULGARIAN', 'ca': 'CATALAN',
    'cs': 'CZECH', 'de': 'GERMAN', 'el': 'GREEK', 'en': 'ENGLISH',
    'eo': 'ESPERANTO', 'es': 'SPANISH', 'fa': 'PERSIAN', 'fi': 'FINNISH',
    'fr': 'FRENCH', 'he': 'HEBREW', 'hr': 'CROATIAN', 'id': 'INDONESIAN',
    'it': 'ITALIAN', 'ko': 'KOREAN', 'nl': 'DUTCH', 'no': 'NORWEGIAN',
    'pl': 'POLISH', 'pt': 'PORTUGUESE', 'ro': 'ROMANIAN', 'ru': 'RUSSIAN',
    'sk': 'SLOVAK', 'sl': 'SLOVENE', 'sr': 'SERBIAN', 'sv': 'SWEDISH',
    'ta': 'TAMIL', 'th': 'THAI', 'tr': 'TURKISH', 'uk': 'UKRAINIAN',
    'zh': 'CHINESE',
}

_PROMPT = (
    'Identify the language of the text given by the user. Reply with the '
    'ISO 639-1 code only: exactly two lowercase letters, nothing else. '
    'If the language cannot be determined, reply with xx.'
)


class LanguageDetectionUnavailable(RuntimeError):
    """Der LLM-Dienst hat nicht geantwortet. Absichtlich laut (HTTP 500 beim
    Speichern) statt eines falschen "Sprache nicht erkannt": der Betreiber
    soll es im Log sehen, der Nutzer soll nicht umformulieren."""


@dataclass(frozen=True)
class IsoCode639_1:
    name: str  # wie lingua: Grossbuchstaben, 'DE'


@dataclass(frozen=True)
class Language:
    name: str  # wie lingua: 'GERMAN'
    iso_code_639_1: IsoCode639_1

    @classmethod
    def from_code(cls, code):
        return cls(_NAMES.get(code, code.upper()), IsoCode639_1(code.upper()))


@dataclass(frozen=True)
class ConfidenceValue:
    language: Language
    value: float


class LanguageDetector:
    def __init__(self):
        self.url = os.environ.get('WGER_LLM_URL', '').rstrip('/')
        self.key = os.environ.get('WGER_LLM_API_KEY', '')
        self.model = os.environ.get('WGER_LLM_MODEL', '')
        self.timeout = float(os.environ.get('WGER_LLM_TIMEOUT', '15'))

    def _ask(self, text):
        if not self.url or not self.model:
            raise LanguageDetectionUnavailable(
                'WGER_LANGUAGE_DETECTOR=llm, aber WGER_LLM_URL/WGER_LLM_MODEL fehlen '
                '(Bindung wger-llm, siehe cf/settings.py)'
            )
        body = {
            'model': self.model,
            'temperature': 0,
            'max_tokens': 5,
            'messages': [
                {'role': 'system', 'content': _PROMPT},
                {'role': 'user', 'content': text},
            ],
        }
        headers = {'Authorization': f'Bearer {self.key}'} if self.key else {}
        try:
            r = requests.post(f'{self.url}/chat/completions', json=body, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            return r.json()['choices'][0]['message']['content']
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as e:
            logger.error('LLM-Spracherkennung fehlgeschlagen: %s', e)
            raise LanguageDetectionUnavailable(str(e)) from e

    def detect_language_of(self, text):
        answer = self._ask(text).strip().lower()
        # Nur eine Antwort der Form "de" zaehlt; "xx", Saetze oder Leeres
        # heissen "nicht erkannt", wie None bei lingua.
        m = re.fullmatch(r'[a-z]{2}', answer)
        if not m or answer == 'xx':
            logger.info('LLM-Spracherkennung ohne Ergebnis, Antwort: %r', answer)
            return None
        return Language.from_code(answer)

    def compute_language_confidence_values(self, text):
        # Ein LLM liefert keine Verteilung; Upstream schreibt den Wert nur ins
        # Debug-Log. Ein zweiter Aufruf nur dafuer lohnt nicht.
        return []


class LanguageDetectorBuilder:
    @classmethod
    def from_all_languages(cls):
        return cls()

    @classmethod
    def from_languages(cls, *languages):
        return cls()

    def build(self):
        return LanguageDetector()
