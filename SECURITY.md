# Sicherheit und Einsatzgrenzen

- Die Anwendung ist für eine lokale Vorführung vorgesehen. Die Testkonten können
  ohne Passwort gewechselt werden. Nicht öffentlich bereitstellen und keine
  vertraulichen Daten importieren. Eine Rollenprüfung mit Demo-Identitäten ist
  keine Unternehmensanmeldung.
- Vor echtem Betrieb wären unter anderem SSO, belastbares Berechtigungsmanagement,
  TLS, sichere Sitzungsverwaltung, Lösch- und Aufbewahrungsregeln, Backups,
  Monitoring, Schutz vor Missbrauch und eine Datenschutzprüfung erforderlich.
- Externe Verarbeitung ist nur mit ausdrücklicher Bestätigung möglich. Diese
  Checkbox ersetzt nicht die organisatorische Prüfung der erforderlichen Rechte.
  Aufnahmen werden nicht heimlich erstellt. Ein Modell kann Fehler machen.
- API-Key, Datenbankpasswort und Workflow-Schlüssel gehören nur in die lokale
  `.env` oder eine geeignete Secret-Verwaltung. Eine echte `.env` nicht hochladen.
- Aufnahmen, Datenbanken, Quellen, Berichte und n8n-Ausführungsdaten bleiben lokal
  beziehungsweise in den lokalen Docker-Volumes. Sie sind nicht für GitHub bestimmt.
  n8n-Ausführungen können vollständige Textabschnitte enthalten.
- Eine Rohaufnahme wird nach erfolgreicher Transkription gelöscht. Bei einem
  Fehler bleibt sie für Wiederholungen gespeichert. Historische Text- und
  Protokollversionen werden nicht automatisch gelöscht.
- Das Modell kann keine externen Aktionen ausführen. Freigaben und Exporte sind
  getrennte, geschützte Anwendungsschritte. Belegprüfung verringert Fehler, beweist
  jedoch keine fachliche Richtigkeit.
- Ein öffentlicher Quellcode-Upload ist keine Erlaubnis, den API-Key des Autors
  zu benutzen. Jede andere Person benötigt für echte Verarbeitung einen eigenen Key.
