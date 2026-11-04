param([int]$Port = 8030)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot 'frontend-tools.ps1')
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 installieren und erneut starten.' }
}
& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check --no-input -r backend/requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Python-Abhängigkeiten konnten nicht installiert werden.' }
Push-Location frontend
try {
    & $Pnpm install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw 'Frontend-Abhängigkeiten fehlen.' }
    & $Pnpm build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend-Build fehlgeschlagen.' }
} finally { Pop-Location }
$env:WORKFLOW_MODE = 'local'
$env:DATABASE_URL = 'sqlite:///./data/meetings.db'
$env:ALLOWED_ORIGINS = "[`"http://localhost:$Port`",`"http://127.0.0.1:$Port`"]"
Write-Output "Besprechungsprotokolle: http://localhost:$Port"
& .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port
