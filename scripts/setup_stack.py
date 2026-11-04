import argparse
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def configuration():
    path = ROOT / ".env"
    if not path.exists():
        shutil.copyfile(ROOT / ".env.example", path)
    values = dict(dotenv_values(path))
    for key in ("WORKFLOW_TOKEN", "N8N_ENCRYPTION_KEY", "POSTGRES_PASSWORD"):
        if not values.get(key):
            values[key] = secrets.token_hex(32)
            set_key(path, key, values[key])
    for key, value in {"APP_PORT": "8030", "N8N_PORT": "5680"}.items():
        if not values.get(key):
            values[key] = value
            set_key(path, key, value)
    return values


def run(*args, payload=None):
    return subprocess.run(args, cwd=ROOT, input=payload, text=True, check=True)


def wait_for(url):
    for _ in range(90):
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(2)
    raise RuntimeError(f"Dienst nicht erreichbar: {url}")


def install(values):
    wait_for(f"http://localhost:{values['N8N_PORT']}/healthz")
    target = "/tmp/meeting-credentials.json"
    credentials = json.dumps(
        [
            {
                "id": "meetingBackend",
                "name": "Besprechungen Backend",
                "type": "httpHeaderAuth",
                "data": {"name": "X-Workflow-Key", "value": values["WORKFLOW_TOKEN"]},
            }
        ]
    )
    write = "const fs=require('fs');let s='';process.stdin.setEncoding('utf8');process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>fs.writeFileSync(process.argv[1],s,{mode:0o600}));"
    try:
        run("docker", "compose", "exec", "-T", "n8n", "node", "-e", write, target, payload=credentials)
        run("docker", "compose", "exec", "-T", "n8n", "n8n", "import:credentials", f"--input={target}")
    finally:
        run(
            "docker",
            "compose",
            "exec",
            "-T",
            "n8n",
            "node",
            "-e",
            "require('fs').rmSync(process.argv[1],{force:true});",
            target,
        )
    run("docker", "compose", "exec", "-T", "n8n", "n8n", "import:workflow", "--input=/workflows/meeting-notes.json")
    run("docker", "compose", "exec", "-T", "n8n", "n8n", "publish:workflow", "--id=meetingNotes")
    run("docker", "compose", "restart", "n8n")
    wait_for(f"http://localhost:{values['N8N_PORT']}/healthz")
    wait_for(f"http://localhost:{values['APP_PORT']}/api/health")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--configure-only", action="store_true")
    args = parser.parse_args()
    values = configuration()
    if args.prepare:
        print("Lokale Konfiguration vorbereitet; Geheimnisse bleiben in .env.")
        return
    run("docker", "info", "--format", "{{.ServerVersion}}")
    if not args.configure_only:
        run("docker", "compose", "up", "-d", "--build")
    install(values)
    print(f"Anwendung: http://localhost:{values['APP_PORT']}")
    print(f"n8n: http://localhost:{values['N8N_PORT']}")
    print("Beim ersten Öffnen von n8n ein eigenes lokales Konto anlegen. Workflow: Besprechungsprotokolle.")


if __name__ == "__main__":
    main()
