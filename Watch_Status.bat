@echo off
title DocuLens Health Watch - Last Checks
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if(Test-Path '.\data\logs\health-watch.jsonl'){Get-Content '.\data\logs\health-watch.jsonl' -Tail 12}else{Write-Output 'No checks recorded yet.'}"
echo.
echo To run an immediate check: powershell -ExecutionPolicy Bypass -File Watch_DocuLens.ps1
pause
