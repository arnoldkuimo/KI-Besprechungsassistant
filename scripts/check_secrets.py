"""Projektdateien und optional die Git-Historie vor einer Veröffentlichung prüfen."""

import argparse
import io
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--worktree", action="store_true", help="Alle versionierten und nicht ignorierten Dateien prüfen"
    )
    parser.add_argument("--history", action="store_true", help="Zusätzlich alle erreichbaren Git-Dateiversionen prüfen")
    args = parser.parse_args()
    paths = (
        (
            git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
            if args.worktree
            else git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
        )
        .decode()
        .split("\0")
    )
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
    checked = 0

    def check(path, content, *, history=False):
        name = Path(path)
        label = f"{path} (Historie)" if history else path
        if (
            name.name == ".env"
            or (name.name.startswith(".env.") and name.name != ".env.example")
            or any(
                part in (".cache", ".pytest_cache", ".ruff_cache", "__pycache__", "data", ".venv", "node_modules")
                for part in name.parts
            )
            or name.suffix in (".db", ".sqlite", ".pem", ".key", ".log")
        ):
            errors.append(f"Nicht veröffentlichen: {label}")
        content = content.decode("utf-8", errors="ignore")
        if any(secret in content for secret in secrets) or re.search(
            r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{35,}|github_pat_[A-Za-z0-9_]{35,}|ghp_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)",
            content,
        ):
            errors.append(f"Mögliche Zugangsdaten in: {label}")

    for path in sorted(set(filter(None, paths))):
        if args.worktree:
            target = ROOT / path
            if not target.exists():
                continue
            if not target.resolve().is_relative_to(ROOT):
                errors.append(f"Pfad außerhalb des Projekts: {path}")
                continue
            content = target.read_bytes()
        else:
            content = git("show", f":{path}")
        check(path, content)
        checked += 1

    versions = 0
    if args.history:
        objects = dict(
            line.split(" ", 1) for line in git("rev-list", "--objects", "--all").decode().splitlines() if " " in line
        )
        stream = io.BytesIO(
            subprocess.check_output(
                ["git", "-c", f"safe.directory={ROOT.as_posix()}", "cat-file", "--batch"],
                input="".join(f"{oid}\n" for oid in objects).encode(),
                cwd=ROOT,
            )
        )
        while header := stream.readline():
            oid, kind, size = header.decode().strip().split()
            content = stream.read(int(size))
            stream.read(1)
            if kind == "blob":
                check(objects[oid], content, history=True)
                versions += 1
    if errors:
        raise SystemExit("\n".join(sorted(set(errors))))
    print(f"Geheimnisprüfung erfolgreich: {checked} Dateien, {versions} historische Dateiversionen.")


if __name__ == "__main__":
    main()
