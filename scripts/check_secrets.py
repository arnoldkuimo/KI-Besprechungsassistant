"""Vor einer Veröffentlichung ausschließlich die zum Commit vorgemerkten Dateien prüfen."""

import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT)


def main():
    paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")
    local = dotenv_values(ROOT / ".env") if (ROOT / ".env").exists() else {}
    secrets = [
        value
        for key, value in local.items()
        if value
        and len(value) >= 20
        and any(word in key for word in ("KEY", "TOKEN", "PASSWORD"))
        and not value.startswith("local-demo-")
    ]
    errors = []
    for path in filter(None, paths):
        name = Path(path)
        if (
            name.name == ".env"
            or (name.name.startswith(".env.") and name.name != ".env.example")
            or any(part in (".cache", "data", ".venv", "node_modules") for part in name.parts)
            or name.suffix in (".db", ".sqlite", ".pem", ".key", ".log")
        ):
            errors.append(f"Nicht veröffentlichen: {path}")
            continue
        content = git("show", f":{path}").decode("utf-8", errors="ignore")
        if any(secret in content for secret in secrets) or re.search(
            r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{35,}|github_pat_[A-Za-z0-9_]{35,}|ghp_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)",
            content,
        ):
            errors.append(f"Mögliche Zugangsdaten in: {path}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Geheimnisprüfung erfolgreich: {len(list(filter(None, paths)))} vorgemerkte Dateien.")


if __name__ == "__main__":
    main()
