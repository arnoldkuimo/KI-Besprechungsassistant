# Prüfstand vom 7. November 2026

## Tatsächlich ausgeführt

| Prüfung | Ergebnis |
| --- | --- |
| Backend-Tests mit isolierten SQLite-Datenbanken | 25 bestanden |
| Frontend-Unit-Tests | 2 bestanden |
| TypeScript und Vite-Produktionsbuild | erfolgreich |
| Ruff-Prüfung und Formatprüfung | erfolgreich |
| Syntax der drei PowerShell-Skripte | keine Parserfehler |
| Installation der gesperrten Python-Abhängigkeiten in eigener virtueller Umgebung | erfolgreich |
| Vollständiger lokaler PowerShell-Start mit anschließendem HTTP- und Browsertest auf Port 8032 | erfolgreich |
| HTTP-Integrationsablauf mit lokalem Worker | erfolgreich |
| Playwright: Erfassung, Bearbeitung, Quellenbeleg, Freigabe, Export, Aufgabenstatus, Kontentrennung | erfolgreich |
| Browseransichten mit 1440 × 1000 und 390 × 844 Pixeln | kein horizontaler Seitenüberlauf, keine JavaScript-Laufzeitfehler |
| Echte OpenAI-Textauswertung mit fiktiven Notizen | erfolgreich mit gpt-4.1-mini, passende Belege und keine Prüfhinweise |
| Echte Audio-Transkription | erfolgreich mit gpt-transcribe und einem öffentlichen synthetischen OpenAI-Stimmbeispiel |
| Docker Compose, PostgreSQL und n8n mit echter OpenAI-Auswertung | Quelle, Auswertung, Belege, Freigabe, Markdown/CSV, Aufgabenstatus und Kontentrennung erfolgreich |
| Audio-Gesamtablauf über die laufende Anwendung | Upload, Transkription, Auswertung, n8n, PostgreSQL, Belege, Freigabe und Markdown-Export erfolgreich |
| Workflow-Export: getrennte Phasen, Header-Authentifizierung, Fehlerpfade | automatisiert geprüft |
| Projektdateien und erreichbare Git-Historie auf lokale Geheimnisse prüfen | erfolgreich |

Der API-Test lieferte eine belegte Zusammenfassung, eine Entscheidung, eine Aufgabe
mit ausdrücklich genanntem Datum und eine offene Frage. Es entstanden keine
Prüfhinweise. Dies sind gezielte Funktionstests, kein umfassender Qualitätsbenchmark.

Der Audio-Import wurde zunächst mit einem Ersatz-Transkriptionsdienst getestet:
Erlaubnisprüfung, Dateiformatprüfung, privater Speicherpfad, Übernahme des Textes und
Entfernung der Rohdatei nach Erfolg. Am 7. November wurden zusätzlich die echte
Transkription und der gesamte Audio-Ablauf bis zum freigegebenen Protokoll geprüft.
Die Aufnahme stammt aus dem öffentlichen synthetischen OpenAI-Stimmbeispiel
unter https://cdn.openai.com/API/docs/audio/alloy.wav. Sie wurde nur im ignorierten
lokalen Cache gespeichert und wird nicht veröffentlicht.

Die Backend-Tests decken insbesondere ab:

- Fremde Konten erhalten keinen Zugriff auf Besprechungen und Exporte.
- Ersteller können nicht selbst als zugewiesene Prüfer freigeben.
- Veraltete Entwurfsstände erzeugen einen Konflikt statt eines Überschreibens.
- Alte Quellenaufträge können nach einer Ersetzung nicht mehr speichern.
- Abgelaufene Reservierungen werden nicht akzeptiert.
- Wiederholtes Speichern erzeugt keine doppelte Protokollversion.
- Freigegebene historische Versionen bleiben nach einer Bearbeitung unverändert.
- Nicht belegte Zuständigkeiten und Termine bleiben offen.
- Prüfhinweise erfordern eine ausdrückliche Bestätigung vor Freigabe.
- Exporte vor Freigabe sind gesperrt; Tabellenformeln werden entschärft.
- Externe Verarbeitung ohne Zustimmung wird abgelehnt.
- Interne Modellaufrufe nutzen ein festes Ausgabeformat und `store=False`.
- Fehlender API-Zugang verhindert einen neuen kostenpflichtigen Auftrag.
- Ungültige oder leere Modellausgaben erzeugen keinen freigabefähigen Entwurf.
- Externe Fehler geben weder Schlüssel noch technische Originalmeldungen preis.
- Der Transkriptionsadapter überträgt die ausgewählte Datei an das konfigurierte Modell.

## Noch nicht vollständig geprüft

- **Wiederanlauf und Backups:** kein vollständiger Neustart-/Wiederherstellungstest
  des laufenden Docker-Stacks. Die Unterbrechungs- und Wiederholungslogik ist in
  isolierten Backend-Tests abgedeckt.
- **Unternehmensbetrieb:** keine SSO-, Last-, Penetrations-, Backup-/Restore- oder
  organisatorische Datenschutzabnahme.
- **Modellqualität im Alltag:** keine repräsentative Auswertung langer, mehrdeutiger
  oder schlecht transkribierter Besprechungen.
- **GitHub Actions:** der lokale Testnachweis ersetzt keinen erfolgreichen CI-Lauf.
  Dieser ist nach der Veröffentlichung separat zu kontrollieren.

Der Docker-Start erfolgte aus einer normalen Windows-PowerShell. Die laufenden
Dienste wurden anschließend über ihre lokalen HTTP-Endpunkte geprüft. Eine frühe
Anfrage vor der Workflow-Registrierung schlug erwartbar fehl; nach abgeschlossenem
Setup war der n8n-Gesamttest erfolgreich. Mit Tests erst beginnen, wenn das
Startskript die fertigen Anwendungsadressen ausgegeben hat.

## Bekannter Hinweis

Starlettes TestClient meldet eine Deprecation-Warnung für die installierte
httpx-Anbindung. Die Tests bestehen; dieser Hinweis bleibt bei einem späteren
Abhängigkeitsupdate zu bearbeiten.

## Browserbilder

Die Bilder in `screenshots/` enthalten ausschließlich das fiktive Beispiel und
die lokalen Testkonten. Es wurden weder Schlüssel noch echte Besprechungsinhalte
in die Bilder aufgenommen.
