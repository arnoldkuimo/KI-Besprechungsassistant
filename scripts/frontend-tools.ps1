$ErrorActionPreference = 'Stop'
$runtime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    $nodeDirectory = Join-Path $runtime 'node\bin'
    if (Test-Path -LiteralPath (Join-Path $nodeDirectory 'node.exe')) {
        $env:PATH = "$nodeDirectory;$env:PATH"
    } else { throw 'Node.js 22 oder neuer installieren oder den Docker-Start verwenden.' }
}
if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    $script:Pnpm = (Get-Command pnpm).Source
} else {
    $script:Pnpm = Join-Path $runtime 'bin\fallback\pnpm.cmd'
    if (-not (Test-Path -LiteralPath $script:Pnpm)) {
        throw 'pnpm fehlt. pnpm 11 installieren oder den Docker-Start verwenden.'
    }
}
