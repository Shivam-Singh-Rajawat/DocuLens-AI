param()
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$python=Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "DocuLens Python environment is missing."
    exit 2
}
& $python -m scripts.health_watch
exit $LASTEXITCODE
