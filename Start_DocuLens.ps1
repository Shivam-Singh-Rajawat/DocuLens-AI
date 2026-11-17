param([switch]$NoBrowser)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$healthUrl = "http://127.0.0.1:8000/api/health"

function Test-DocuLensReady {
    try {
        $result = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        return ($result.status -eq "ok" -and $null -ne $result.embedding_backend)
    } catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Created .env. Add a Gemini key there to enable AI-generated answers."
}
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creating Python 3.11 environment..."
    & py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Unable to create Python 3.11 environment." }
}
if (-not (Test-DocuLensReady)) {
    & $python -m pip show fastapi uvicorn chromadb sentence-transformers google-genai psycopg *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing missing dependencies..."
        & $python -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    }
    # Auto-start DocuLens isolated local PostgreSQL after system reboots.
    if (Select-String -Path ".env" -Pattern "^METADATA_BACKEND=postgres\s*$" -Quiet) {
        & $python -m scripts.pg_local start
        if ($LASTEXITCODE -ne 0) { throw "Local DocuLens PostgreSQL startup failed." }
    }
    New-Item -ItemType Directory -Force -Path ".\data\logs" | Out-Null
    $stdout = Join-Path $PSScriptRoot "data\logs\uvicorn.out.log"
    $stderr = Join-Path $PSScriptRoot "data\logs\uvicorn.err.log"
    $proc = Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "doculens.api:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $PSScriptRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
    $ready = $false
    for ($i = 0; $i -lt 50; $i++) {
        Start-Sleep -Milliseconds 400
        if (Test-DocuLensReady) { $ready = $true; break }
        if ($proc.HasExited) { break }
    }
    if (-not $ready) {
        Get-Content -LiteralPath $stderr -Tail 15 -ErrorAction SilentlyContinue
        throw "DocuLens did not start. Check data\logs for details."
    }
    Write-Host "Server started (process ID $($proc.Id))."
} else {
    Write-Host "DocuLens is already running."
}
Write-Host "Dashboard: http://127.0.0.1:8000"
Write-Host "API docs:  http://127.0.0.1:8000/docs"
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:8000/" }
