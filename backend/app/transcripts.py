from datetime import date
import re
import textwrap

from .schemas import Report


def segments_from_text(text: str, participants: list[str]) -> list[dict]:
    names = {name.casefold(): name for name in participants}
    segments = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        speaker, timestamp, body = None, None, line
        match = re.match(r"^(?:\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s+)?([^:]{1,100}):\s*(.+)$", line)
        if match and match[2].strip().casefold() in names:
            timestamp, speaker, body = match[1], names[match[2].strip().casefold()], match[3]
        for part in textwrap.wrap(body, width=1200, break_long_words=False, break_on_hyphens=False):
            segments.append({"id": len(segments) + 1, "speaker": speaker, "timestamp": timestamp, "text": part})
    if not segments or len(segments) > 400 or sum(len(s["text"]) for s in segments) > 60000:
        raise ValueError(
            "Die Quelle muss Text enthalten und darf höchstens 60.000 Zeichen oder 400 Abschnitte umfassen."
        )
    return segments


def normalized(text):
    return " ".join(text.split()).casefold()


def validate_report(report: Report, segments: list[dict], participants: list[str], *, manual=False) -> dict:
    available = {s["id"]: s for s in segments}
    result = {"summary": [], "decisions": [], "tasks": [], "open_questions": [], "warnings": [], "manual_edit": manual}
    for section in ("summary", "decisions", "tasks", "open_questions"):
        for item in getattr(report, section):
            sources = [available[i] for i in dict.fromkeys(item.source_ids) if i in available]
            quote = normalized(item.quote)
            found = len(sources) == len(set(item.source_ids)) and any(
                quote in normalized(s["text"])
                or (bool(s["speaker"]) and quote in normalized(f"{s['speaker']}: {s['text']}"))
                for s in sources
            )
            if not found:
                if manual:
                    raise ValueError("Ein Textbeleg passt nicht zu den angegebenen Quellenstellen.")
                result["warnings"].append("Ein Eintrag ohne passenden Textbeleg wurde zurückgehalten.")
                continue
            entry = item.model_dump()
            entry["source_ids"] = [source["id"] for source in sources]
            if section == "tasks":
                text = " ".join(f"{s['speaker'] or ''} {s['text']}" for s in sources)
                if entry["owner"] and (
                    entry["owner"] not in participants
                    or (not manual and normalized(entry["owner"]) not in normalized(text))
                ):
                    entry["owner"] = None
                    result["warnings"].append("Eine nicht belegte Aufgabenverantwortung wurde offengelassen.")
                if entry["due_text"] and not manual and normalized(entry["due_text"]) not in normalized(text):
                    entry["due_text"] = None
                    result["warnings"].append("Eine nicht belegte Frist wurde offengelassen.")
                entry["due_date"] = None
                if entry["due_text"]:
                    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", entry["due_text"])
                    if match:
                        try:
                            entry["due_date"] = date.fromisoformat(match[0]).isoformat()
                        except ValueError:
                            result["warnings"].append("Eine Datumsangabe muss geprüft werden.")
                entry["id"] = f"A{len(result['tasks']) + 1}"
            else:
                entry["id"] = f"{section[0].upper()}{len(result[section]) + 1}"
            result[section].append(entry)
    if not result["summary"]:
        raise ValueError("Es konnte keine ausreichend belegte Zusammenfassung erstellt werden.")
    return result


def editable_report(report: dict) -> dict:
    result = {}
    for section in ("summary", "decisions", "tasks", "open_questions"):
        keys = (
            ("text", "source_ids", "quote", "owner", "due_text")
            if section == "tasks"
            else ("text", "source_ids", "quote")
        )
        result[section] = [{k: item[k] for k in keys} for item in report[section]]
    return result
