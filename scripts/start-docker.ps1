$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 installieren und erneut starten.' }
}
& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check --no-input python-dotenv==1.2.4
if ($LASTEXITCODE -ne 0) { throw 'Setup-Abhängigkeit konnte nicht installiert werden.' }
& .\.venv\Scripts\python.exe scripts/setup_stack.py
if ($LASTEXITCODE -ne 0) { throw 'Docker-Start fehlgeschlagen. Docker Desktop und den freien Port 8030 prüfen.' }
