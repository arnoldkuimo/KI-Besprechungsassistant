import argparse
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8030")
    parser.add_argument("--require-n8n", action="store_true")
    parser.add_argument("--confirm-cost", action="store_true", help="Einen echten Auswertungsauftrag erlauben")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=10) as client:
        meta = client.get("/api/meta").raise_for_status().json()
        if meta["provider"] != "demo" and not args.confirm_cost:
            raise SystemExit(
                "Echter API-Aufruf nur mit --confirm-cost. Es werden ausschließlich fiktive Notizen gesendet."
            )
        if meta["provider"] == "openai":
            assert meta["configured"], "Der lokale OpenAI-Zugang fehlt."
        if args.require_n8n:
            assert meta["workflow_mode"] == "n8n"
        client.post("/api/login", json={"account_id": 1}).raise_for_status()
        meeting = (
            client.post(
                "/api/meetings",
                json={
                    "title": "Integrationsprüfung",
                    "meeting_date": "2026-11-04",
                    "participants": ["Anna Weber", "Malik Brandt"],
                    "reviewer_id": 2,
                    "external_processing_allowed": meta["provider"] == "openai" and args.confirm_cost,
                    "transcript": "Anna Weber: Wir besprechen den Testlauf der Anwendung.\nMalik Brandt: Wir haben entschieden, die Checkliste zu verwenden.\nAnna Weber: Ich erstelle die Auswertung bis 2026-11-12.\nMalik Brandt: Welche Daten fehlen noch?",
                },
            )
            .raise_for_status()
            .json()
        )
        path = f"/api/meetings/{meeting['id']}"
        for _ in range(180):
            detail = client.get(path).raise_for_status().json()
            if detail["meeting"]["status"] in ("draft", "error"):
                break
            time.sleep(1)
        assert detail["meeting"]["status"] == "draft", detail["meeting"]["last_error"]
        assert detail["report"]["tasks"]
        assert detail["report"]["summary"] and detail["report"]["decisions"]
        assert detail["report"]["open_questions"]
        assert any(t["owner"] == "Anna Weber" and t["due_date"] == "2026-11-12" for t in detail["report"]["tasks"])
        assert detail["processing"]["stage"] == "saved"
        assert client.get(path + "/export/md").status_code == 409
        assert client.post(path + "/approve", json={"expected_revision": 1}).status_code == 403
        client.post(path + "/submit", json={"expected_revision": 1}).raise_for_status()
        client.post("/api/login", json={"account_id": 2}).raise_for_status()
        client.post(path + "/approve", json={"expected_revision": 1, "acknowledge_warnings": True}).raise_for_status()
        exported = client.get(path + "/export/md").raise_for_status().text
        assert "Freigegeben von: Malik Brandt" in exported
        task = detail["report"]["tasks"][0]["id"]
        client.put(path + f"/tasks/{task}", json={"revision": 1, "status": "done"}).raise_for_status()
        assert client.get(path).raise_for_status().json()["task_states"][task] == "done"
        assert "done" in client.get(path + "/export/csv").raise_for_status().text
        client.post("/api/login", json={"account_id": 3}).raise_for_status()
        assert client.get(path).status_code == 404
        print(
            f"Integrationsprüfung bestanden ({meta['provider']}, {meta['workflow_mode']}): Quelle, Auswertung, Belege, Freigabe, Export, Aufgaben und Kontentrennung."
        )


if __name__ == "__main__":
    main()
