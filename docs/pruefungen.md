# Prüfstand vom 4. November 2026

## Tatsächlich ausgeführt

| Prüfung | Ergebnis |
| --- | --- |
| Backend-Tests mit isolierten SQLite-Datenbanken | 16 bestanden |
| Frontend-Unit-Tests | 2 bestanden |
| TypeScript und Vite-Produktionsbuild | erfolgreich |
| Ruff-Prüfung und Formatprüfung | erfolgreich |
| Syntax der drei PowerShell-Skripte | keine Parserfehler |
| Installation der gesperrten Python-Abhängigkeiten in eigener virtueller Umgebung | erfolgreich |
| Vollständiger lokaler PowerShell-Start mit anschließendem HTTP- und Browsertest auf Port 8032 | erfolgreich |
| HTTP-Integrationsablauf mit lokalem Worker | erfolgreich |
| Playwright: Erfassung, Bearbeitung, Quellenbeleg, Freigabe, Export, Aufgabenstatus, Kontentrennung | erfolgreich |
| Browseransichten mit 1440 × 1000 und 390 × 844 Pixeln | kein horizontaler Seitenüberlauf, keine JavaScript-Laufzeitfehler |
| Echte OpenAI-Textauswertung mit fiktiven Notizen | erfolgreich, ein Auswertungsaufruf mit gpt-4.1-mini |
| Workflow-Export: getrennte Phasen, Header-Authentifizierung, Fehlerpfade | automatisiert geprüft |
| Vor dem Commit vorgemerkte Dateien auf lokale Geheimnisse prüfen | erfolgreich |

Der API-Test lieferte eine belegte Zusammenfassung, eine Entscheidung, eine Aufgabe
mit ausdrücklich genanntem Datum und eine offene Frage. Es entstanden keine
Prüfhinweise. Dies ist ein einzelner Funktionstest, kein umfassender Qualitätsbenchmark.

Der Audio-Import wurde mit einem Ersatz-Transkriptionsdienst getestet:
Erlaubnisprüfung, Dateiformatprüfung, privater Speicherpfad, Übernahme des Textes und
Entfernung der Rohdatei nach Erfolg. Dabei fand **kein echter Audio-API-Aufruf** statt.

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

## Noch nicht vollständig geprüft

- **Docker Compose, PostgreSQL und die tatsächliche n8n-Ausführung im Verbund:**
  Die Entwicklungsumgebung kann die Docker-Engine nicht ansprechen. Das Setup und
  ein ausführbarer Stack-Test sind vorhanden; daraus wird kein bestandener Test
  des gesamten Stacks abgeleitet.
- **Echte Audio-Transkription:** nur Adapter-/Ablaufprüfung mit Ersatzdienst.
- **Unternehmensbetrieb:** keine SSO-, Last-, Penetrations-, Backup-/Restore- oder
  organisatorische Datenschutzabnahme.
- **Modellqualität im Alltag:** keine repräsentative Auswertung langer, mehrdeutiger
  oder schlecht transkribierter Besprechungen.
- **GitHub-Veröffentlichung:** noch nicht erfolgt. Eine nutzbare GitHub-Anmeldung
  fehlt; der Credential Manager öffnet kein Fenster und seine spätere Geräteanmeldung
  scheitert hier an der Windows-Verbindung. Keine Zugangsdaten wurden veröffentlicht.

Die vorhandene GitHub-Actions-Datei beschreibt diese Prüfungen für einen künftigen
Push. Ein enthaltener CI-Workflow ist kein Nachweis, dass er bereits gelaufen ist.

## Bekannter Hinweis

Starlettes TestClient meldet eine Deprecation-Warnung für die installierte
httpx-Anbindung. Die Tests bestehen; dieser Hinweis bleibt bei einem späteren
Abhängigkeitsupdate zu bearbeiten.

## Browserbilder

Die Bilder in `screenshots/` enthalten ausschließlich das fiktive Beispiel und
die lokalen Testkonten. Es wurden weder Schlüssel noch echte Besprechungsinhalte
in die Bilder aufgenommen.
