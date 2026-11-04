import argparse
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8030")
    parser.add_argument("--require-n8n", action="store_true")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=10) as client:
        meta = client.get("/api/meta").raise_for_status().json()
        assert meta["provider"] == "demo", "Stack-Test nur ohne kostenpflichtige API ausführen."
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
                    "transcript": "Anna Weber: Wir besprechen den Testlauf der Anwendung.\nMalik Brandt: Wir haben entschieden, die Checkliste zu verwenden.\nAnna Weber: Ich erstelle die Auswertung bis 2026-11-12.\nMalik Brandt: Welche Daten fehlen noch?",
                },
            )
            .raise_for_status()
            .json()
        )
        path = f"/api/meetings/{meeting['id']}"
        for _ in range(60):
            detail = client.get(path).raise_for_status().json()
            if detail["meeting"]["status"] in ("draft", "error"):
                break
            time.sleep(1)
        assert detail["meeting"]["status"] == "draft", detail["meeting"]["last_error"]
        assert detail["report"]["tasks"]
        assert detail["processing"]["stage"] == "saved"
        client.post(path + "/submit", json={"expected_revision": 1}).raise_for_status()
        client.post("/api/login", json={"account_id": 2}).raise_for_status()
        client.post(path + "/approve", json={"expected_revision": 1, "acknowledge_warnings": True}).raise_for_status()
        assert client.get(path + "/export/md").status_code == 200
        client.post("/api/login", json={"account_id": 3}).raise_for_status()
        assert client.get(path).status_code == 404
        print(
            f"Integrationsprüfung bestanden ({meta['workflow_mode']}): Quelle, Auswertung, Belege, Freigabe, Export und Kontentrennung."
        )


if __name__ == "__main__":
    main()
