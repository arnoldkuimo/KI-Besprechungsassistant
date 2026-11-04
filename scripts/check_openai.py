import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_check(settings):
    from backend.app.extraction import Extractor
    from backend.app.transcripts import segments_from_text, validate_report

    if settings.provider != "openai" or not settings.openai_api_key:
        raise SystemExit("PROVIDER=openai und einen lokalen OPENAI_API_KEY konfigurieren.")
    participants = ["Anna Weber", "Malik Brandt"]
    text = """Anna Weber: Wir planen den Kundentest für unser Formular.
Malik Brandt: Wir haben entschieden, zuerst nur zwei Arbeitsplätze zu verwenden.
Anna Weber: Ich erstelle die Checkliste bis 2026-11-12.
Malik Brandt: Die Verantwortung für die Geräteliste ist noch offen. Es gibt dafür noch keinen Termin.
Anna Weber: Welche Geräte können wir ausleihen? Das müssen wir noch klären.
"""
    segments = segments_from_text(text, participants)
    report = Extractor(settings).extract(
        {"title": "Kundentest", "date": "2026-11-04", "participants": participants}, segments
    )
    checked = validate_report(report, segments, participants)
    assert checked["summary"] and checked["decisions"] and checked["tasks"] and checked["open_questions"]
    assert any(t["owner"] == "Anna Weber" and t["due_date"] == "2026-11-12" for t in checked["tasks"])
    assert not any(t["owner"] == "Malik Brandt" for t in checked["tasks"])
    print(
        f"Echter API-Test bestanden: {settings.openai_model}; belegte Zusammenfassung, Entscheidung, Aufgabe und offene Frage."
    )
    print(f"Prüfhinweise: {len(checked['warnings'])}. Keine Aufnahme und keine echten Personendaten übertragen.")


if __name__ == "__main__":
    from backend.app.config import Settings

    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-cost", action="store_true")
    args = parser.parse_args()
    if not args.confirm_cost:
        raise SystemExit("Der Test verursacht API-Kosten. Mit --confirm-cost ausdrücklich starten.")
    run_check(Settings())
