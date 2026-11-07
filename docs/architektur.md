# Komponenten und Ablauf

## 1. Erfassung in React

`frontend/src/App.tsx` enthält Besprechungsliste, Erfassung, Protokollansicht,
Quellenprüfung, Bearbeitungsdialog und Aufgabenbereich. `types.ts` beschreibt
die API-Daten; `style.css` enthält das responsive Layout. Die API-Abfragen laufen
vom Browser zum gleichen lokalen Server. Ein API-Key gelangt nicht in den Browser.

Es werden keine Besprechungen vorab angelegt. Drei fiktive Testkonten und ein
ausdrücklich auswählbarer Beispieltext machen den Prüfablauf reproduzierbar.

## 2. API und Rechte

`backend/app/main.py` nimmt Eingaben entgegen, prüft sie mit den Schemas und
ordnet die Besprechung einem Ersteller und einer anderen prüfenden Person zu.
Nur diese beiden Konten dürfen auf Besprechung, Versionen und Exporte zugreifen.
Die Anmeldung verwendet ein HttpOnly-/SameSite-Cookie; gespeichert wird dessen
Hash. Das frei wählbare Testkonto ersetzt dabei keine echte Authentifizierung.

Die internen Workflow-Endpunkte benötigen einen separaten Header-Schlüssel.
Er ist nicht Teil des öffentlichen Workflow-Exports. Das Setup importiert ihn
in n8n als Credential, sodass keine Umgebungsvariable im Editor aufgelöst werden muss.

## 3. Quellen vorbereiten

`transcripts.py` teilt die Quelle in nummerierte Abschnitte auf. Bereits vorhandene
Sprechernamen und Zeitmarken werden übernommen, wenn der Name zur Teilnehmerliste
gehört. Eine Audioaufnahme liefert einfachen Text, keine verlässlich getrennten
Sprecher. Es wird keine Sprechererkennung vorgetäuscht.

Eine Aufnahme benötigt ausdrücklich bestätigte Verarbeitungserlaubnis. Dateigröße,
Endung und grundlegende Dateisignatur werden geprüft. Der private Dateiname wird
zufällig vergeben. Nach erfolgreicher Transkription und Speicherung des Textes
wird die Rohdatei entfernt. Bei einem Fehler bleibt sie für einen erneuten Versuch
im privaten Datenverzeichnis; es gibt keine automatische Aufbewahrungsfrist.

## 4. Inhalte auswerten

`extraction.py` besitzt zwei getrennte Wege:

- `demo`: einfache Schlüsselwortregeln, ohne externen Dienst. Diese Demonstration
  kann keine freien fachlichen Texte zuverlässig verstehen.
- `openai`: strukturierte Ausgabe über `client.responses.parse`. Übertragen werden
  Besprechungsmetadaten und die freigegebenen Textabschnitte. `store=False` wird
  gesetzt; daraus wird keine allgemeine Zusage über die Aufbewahrung beim Anbieter
  abgeleitet. Das Ausgabeformat wird mit Pydantic festgelegt.

Das Projekt nutzt im Text-Test `gpt-4.1-mini`. Die vorhandene Modellkonfiguration
wurde beibehalten und mit dem konkreten Protokollformat getestet. Die Wahl ist
konfigurierbar und bedeutet nicht, dass dieses Modell für jede Besprechung das
beste ist. Für Aufnahmeverarbeitung ist `gpt-transcribe` konfiguriert. Beide
Adapter wurden am 7. November 2026 mit echten API-Aufrufen geprüft; für den
Audio-Test wurde ein öffentliches synthetisches OpenAI-Stimmbeispiel verwendet.

Die Texte der Besprechung sind Nutzdaten, keine Arbeitsanweisungen an die Anwendung.
Das Modell erhält keine Werkzeuge zum Ausführen von Befehlen oder Versenden von
Nachrichten. Es entscheidet auch nicht über die menschliche Freigabe.

API-Verträge: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
und [Speech to text](https://developers.openai.com/api/docs/guides/speech-to-text).

## 5. Belege und Verlässlichkeit

Jeder Eintrag enthält Inhalt, vorhandene Abschnittsnummern und einen Textbeleg.
Die Prüfung gleicht den Beleg mit den angegebenen Abschnitten ab; Großschreibung
und Leerraum werden dabei normalisiert. Ungültige Quellenverweise werden nicht
als fertiges Protokoll übernommen. Nicht belegte Zuständigkeiten oder Fristen
werden offengelassen und als Prüfhinweis vermerkt. Nur ausdrücklich vorhandene
ISO-Daten werden als maschinenlesbares Datum übernommen; „bis Freitag“ bleibt Text.

Wichtig: Ein passender Beleg beweist nicht, dass jede Zusammenfassung semantisch
richtig ist. Ein Zitat könnte falsch interpretiert oder eine wichtige Aussage
ausgelassen werden. Deshalb bleibt die Prüfung durch Menschen Teil des Produkts.
Bei einer bewussten manuellen Korrektur kann der Ersteller eine bekannte Person
oder Frist zuweisen; die Bearbeitung wird als neue Version gespeichert.

## 6. Orchestrierung und Wiederholungen

`service.py` verwaltet Aufträge, Reservierungen und Phasen:

| Phase | Aufgabe |
| --- | --- |
| start | Auftrag exklusiv reservieren, Quelle und Erlaubnis kontrollieren |
| source | Vorhandenen Text laden oder freigegebene Aufnahme transkribieren |
| extract | Strukturierten Bericht ableiten |
| validate | Quellen, Verantwortlichkeiten und Fristen prüfen |
| save | Neue unveröffentlichte Protokollversion speichern |
| fail | Fehler nachvollziehbar am Auftrag und an der Besprechung speichern |

Der Export `workflows/meeting-notes.json` verbindet diese Phasen mit einzelnen
HTTP-Nodes. Jeder Fehlerzweig führt zur Fehlerbehandlung. Ein bereits reservierter
Auftrag wird nicht nochmals verarbeitet. Erfolgreich abgeleitete Inhalte werden
für Wiederholungen zwischengespeichert. Ein wiederholtes Speichern erzeugt keine
zweite Version. Reservierungen laufen ab; nach wiederholten Unterbrechungen bleibt
der Auftrag als Fehler sichtbar. Ein API-Aufruf kann bei einem Netzwerkabbruch
dennoch kostenpflichtig gewesen sein, auch wenn kein Ergebnis gespeichert wurde.

Wenn eine Quelle ersetzt wird, verlieren alte Aufträge ihre Berechtigung zum
Speichern. Sie dürfen den neueren Stand nicht überschreiben. Das Ergebnis einer
alten Modellanfrage wird nach dem Rückruf nochmals gegen die Reservierung geprüft.

## 7. Versionen und Freigabe

`models.py` trennt Besprechung, Quellenversion, Protokollversion, Auftrag,
Aufgabenstatus und Historieneintrag. `current_revision` und erwartete Versionsnummern
verhindern das versehentliche Überschreiben eines inzwischen geänderten Entwurfs.

Der Ersteller reicht eine Version ein. Nur die zugewiesene andere Person kann sie
freigeben oder Änderungen erbitten. Vorhandene Prüfhinweise erfordern eine
ausdrückliche Bestätigung. Frühere freigegebene Protokolle bleiben erhalten; eine
spätere Änderung ist ein neuer Entwurf und keine nachträgliche Änderung der Freigabe.

Markdown und CSV verwenden nur freigegebene Versionen. Aufgabenstatus wird getrennt
vom Protokollinhalt geführt. CSV-Ausgaben entschärfen führende Tabellenformeln;
der Browser stellt Inhalte als Text dar, nicht als ausführbares HTML.

## 8. Infrastruktur

Der lokale Start verwendet SQLite. Compose sieht PostgreSQL, die Anwendung und
eine eigene n8n-Instanz vor. Öffentliche Host-Ports sind nur an `127.0.0.1` gebunden.
Es werden keine vorhandenen n8n-Installationen oder Datenbanken zurückgesetzt.
Die Volumes bleiben bei einem normalen `docker compose down` erhalten.

Tests verwenden ausschließlich isolierte Datenbanken und fiktive Inhalte. Der
aktuelle Nachweis und nicht ausführbare Prüfungen stehen in `pruefungen.md`.
