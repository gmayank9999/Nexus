$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Create .venv and install services/nexus_server[dev] before running checks."
}

Push-Location (Join-Path $repositoryRoot "services\nexus_server")
try {
    & $python -m ruff format --check --no-cache .
    & $python -m ruff check --no-cache .
    & $python -m mypy app
    & $python -m pytest -p no:cacheprovider
}
finally {
    Pop-Location
}

Push-Location (Join-Path $repositoryRoot "apps\nexus_flutter")
try {
    dart format --output=none --set-exit-if-changed lib test
    flutter analyze
    flutter test
}
finally {
    Pop-Location
}

