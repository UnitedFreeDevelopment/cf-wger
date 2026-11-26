# Berichte von der Zielplattform

Der Weg zurück vom Agenten auf der Zielplattform zum Entwickler auf
`cfk8s`. Der Agent hat nur den Clone und einen Branch; der Chat ist kein
Kanal, und `cf/README.md` ist für das da, was *gilt*, nicht für das, was
unterwegs auffiel. Deshalb: ein Bericht je Sache, als Datei hier, auf seinem
Branch ab `cf-port`. Der Entwickler liest sie nach dem Merge, setzt um und
trägt im Bericht ein, was daraus wurde.

## Wann ein Bericht fällig ist

- **fehler**: etwas ging nicht. Immer, auch wenn es umgangen wurde.
- **abweichung**: Anleitung oder README sagen etwas, die Plattform etwas
  anderes.
- **messung**: ein Wert, der in der Doku als „bitte prüfen" oder „nicht
  gemessen" steht, ist jetzt gemessen. Zusätzlich zur Korrektur in
  `cf/README.md`, damit nachvollziehbar bleibt, wie.
- **optimierung**: es geht, aber es ginge besser (kleiner, schneller,
  einfacher).
- **frage**: der Agent braucht eine Entscheidung und hat nach eigener
  Vorgabe weitergemacht.

Ein Bericht je Sache, nicht einer je Tag: Einzelberichte lassen sich einzeln
abschließen.

## Datei

`cf/berichte/JJJJ-MM-TT-<typ>-<kurzname>.md`, zum Beispiel
`2026-12-02-fehler-staging-pip-index.md`. Vorlage: `VORLAGE.md`, kopieren
und ausfüllen. Berichte und Änderungen an `cf/README.md` in getrennten
Commits.

## Kopf

YAML-Frontmatter, alle Felder Pflicht:

| Feld | Werte |
|---|---|
| `datum` | `JJJJ-MM-TT` |
| `typ` | `fehler`, `abweichung`, `messung`, `optimierung`, `frage` |
| `schwere` | `blockiert` (ging nicht weiter), `umgangen` (ging mit Umweg weiter), `hinweis` |
| `schritt` | Nummer des Schritts in `cf/ANLEITUNG-ZIELPLATTFORM.md`; `0` außerhalb |
| `variante` | `VARIANT` beim Vorfall: `cnb` oder `buildpack` |
| `detector` | `DETECTOR` beim Vorfall: `lingua` oder `llm` |
| `plattform` | `tas` oder `vanilla` |
| `status` | `offen` beim Anlegen. Auf `verarbeitet` oder `verworfen` setzt **nur der Entwickler**, mit Datum und Commit in „Ergebnis" |

## Rumpf

Sechs Abschnitte, in dieser Reihenfolge, Überschriften genau so. Ein
Abschnitt ohne Inhalt trägt einen Strich, wird nicht weggelassen.

1. **Beobachtung.** Was passiert ist, mit der Ausgabe im Wortlaut in einem
   Codeblock. Anonymisiert: Versionen ja; Hostnamen, Adressen, Tokens,
   Vorgangsnummern, Namen von Personen nein.
2. **Erwartung.** Was Anleitung oder README an der Stelle sagen, mit Datei
   und Abschnitt.
3. **Ursache.** Zwei Unterpunkte, `verifiziert` und `Hypothese`. Eine
   Hypothese darf stehen, muss aber so heißen. Verifiziert heißt: die
   Gegenprobe ist gelaufen und steht dabei.
4. **Getan.** Befehle und Änderungen des Agenten, als Diff oder
   Befehlsfolge. Nichts, was nicht wirklich gelaufen ist.
5. **Vorschlag.** Was der Entwickler ändern soll: Datei, Stelle, warum.
6. **Messwerte.** Tabelle mit den Spalten `Was | Wert | Einheit | Wie
   gemessen`.

Dahinter, nur vom Entwickler: **Ergebnis.** Was aus dem Bericht wurde,
mit Datum und Commit.

## Wie der Entwickler abarbeitet

Nach dem Merge jeden Bericht mit `status: offen` lesen, in dieser
Reihenfolge: `blockiert` vor `umgangen` vor `hinweis`. Je Bericht entweder
die Änderung im Repo machen und den Bericht auf `verarbeitet` setzen, oder
begründet auf `verworfen`. Beides im Abschnitt „Ergebnis", mit Commit. Der
Bericht bleibt liegen; die Historie steht hier, nicht in `cf/README.md`.
