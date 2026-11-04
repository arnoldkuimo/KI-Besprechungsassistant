# Besprechungsprotokolle

## Ziel und Umfang

Aus Besprechungsnotizen oder einem Transkript entstehen nachvollziehbare,
prüfbare Protokolle mit Entscheidungen und Aufgaben. Eine Aufnahme kann nach
bestätigter Berechtigung und Zustimmung zur Übertragung extern transkribiert werden.
Es gibt keine versteckte Aufnahme, automatische Meeting-Teilnahme oder ungefragte E-Mail.

## Fachlicher Ablauf

1. Titel, Datum, Teilnehmende, prüfende Person und Quelle erfassen.
2. Die Quelle in nummerierte Textabschnitte aufteilen.
3. Zusammenfassung, Entscheidungen, Aufgaben und offene Fragen extrahieren.
4. Quellenstellen und wörtliche Belege prüfen. Unbelegte Angaben zurückhalten.
5. Einen Entwurf speichern. Zuständigkeiten und Fristen werden nicht erfunden.
6. Der Ersteller kann den Entwurf bearbeiten und zur Prüfung vorlegen.
7. Die zugewiesene prüfende Person kann Änderungen verlangen oder freigeben.
8. Freigegebene Versionen bleiben nachvollziehbar. Markdown- und Aufgaben-CSV-Export
   sind erst nach der Freigabe möglich.

## Architektur

React und TypeScript stellen Besprechungsliste, Protokollprüfung, Quellenansicht und
Aufgaben dar. FastAPI kapselt Rechte, Datenzugriff und Verarbeitung. PostgreSQL ist
für den Compose-Stack vorgesehen; SQLite ermöglicht einen einfachen lokalen Start.
n8n steuert die einzelnen Verarbeitungsschritte über geschützte Backend-Endpunkte.
Ohne n8n ruft der lokale Worker dieselben Schritte auf. OpenAI ist optional; ohne Key
gibt es ausschließlich eine klar begrenzte lokale Demonstration.

## Prüfbare Kriterien

- Ersteller und zugewiesene prüfende Person sehen dieselbe Besprechung; fremde Konten nicht.
- Jeder extrahierte Inhalt verweist auf vorhandene Abschnitte und einen passenden Textbeleg.
- Fehlende Zuständigkeit oder Frist bleibt leer und sichtbar klärungsbedürftig.
- Ein Entwurf wird nicht automatisch freigegeben oder extern versendet.
- Alte Hintergrundaufrufe dürfen neuere Bearbeitungen nicht überschreiben.
- Wiederholte Workflow-Aufrufe erzeugen keine doppelten Protokollversionen.
- Änderungen und Freigaben werden mit Version, Zeitpunkt und Person festgehalten.
- Exporte verwenden nur freigegebene Daten; CSV-Felder sind gegen Tabellenformeln abgesichert.
- Schlüssel, Aufnahmen, Protokolle und lokale Datenbanken werden nicht auf GitHub veröffentlicht.

## Grenzen

Die lokalen Konten dienen der Vorführung und ersetzen keine Unternehmensanmeldung.
Eine Quellenprüfung beweist nicht die semantische Richtigkeit jeder Aussage.
Die menschliche Prüfung bleibt erforderlich. Es gibt keine SSO-, Kalender-, Teams-,
Zoom- oder Jira-Integration. Diese wären gesonderte Anforderungen.
