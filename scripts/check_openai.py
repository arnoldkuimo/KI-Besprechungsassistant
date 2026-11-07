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


def check_audio(settings, path):
    from backend.app.extraction import Extractor

    if settings.provider != "openai" or not settings.openai_api_key.strip():
        raise SystemExit("PROVIDER=openai und einen lokalen OPENAI_API_KEY konfigurieren.")
    if not path.is_file() or not 44 <= path.stat().st_size <= 25 * 1024 * 1024:
        raise SystemExit("Eine freigegebene Testaufnahme mit höchstens 25 MB auswählen.")
    text = Extractor(settings).transcribe(path)
    assert len(text.strip()) >= 30, "Die Transkription enthält zu wenig Text."
    print(
        f"Echte Audio-Transkription bestanden: {settings.transcription_model}; {len(text)} Zeichen. Inhalt nicht ausgegeben."
    )


if __name__ == "__main__":
    from backend.app.config import Settings

    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-cost", action="store_true")
    parser.add_argument(
        "--audio", type=Path, help="Statt Textauswertung eine ausdrücklich freigegebene Testaufnahme transkribieren"
    )
    args = parser.parse_args()
    if not args.confirm_cost:
        raise SystemExit("Der Test verursacht API-Kosten. Mit --confirm-cost ausdrücklich starten.")
    try:
        if args.audio:
            check_audio(Settings(), args.audio)
        else:
            run_check(Settings())
    except Exception as error:
        from backend.app.extraction import public_error

        raise SystemExit(f"API-Test fehlgeschlagen ({type(error).__name__}): {public_error(error)}") from None
