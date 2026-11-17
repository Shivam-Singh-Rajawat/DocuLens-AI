param([switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$connections = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
foreach ($conn in $connections) {
    $ownerId = [int]$conn.OwningProcess
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerId"
    if ($null -eq $process) { continue }
    if ($process.CommandLine -notmatch "doculens\.api:app") {
        throw "Port 8000 belongs to another application; refusing to terminate it."
    }
    Write-Host "Stopping DocuLens process $ownerId..."
    Stop-Process -Id $ownerId -Force
}
Start-Sleep -Milliseconds 700
& (Join-Path $PSScriptRoot "Start_DocuLens.ps1") -NoBrowser:$NoBrowser
