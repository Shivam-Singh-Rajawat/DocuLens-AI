@echo off
title DocuLens AI - Local Verification
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment not found. Run Start_DocuLens.bat first.
  if not defined DOCULENS_VERIFY_CI pause
  exit /b 1
)
echo [1/3] PostgreSQL status
".venv\Scripts\python.exe" -m scripts.pg_local status
if errorlevel 1 goto fail
echo.
echo [2/3] Automated unit and API tests
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto fail
echo.
echo [3/3] Live RAG retrieval evaluation
".venv\Scripts\python.exe" -m scripts.evaluate_local
if errorlevel 1 goto fail
echo.
echo ALL CHECKS PASSED. The local RAG server remains available at http://127.0.0.1:8000
if not defined DOCULENS_VERIFY_CI pause
exit /b 0
:fail
echo.
echo A CHECK FAILED. Read the output above and inspect data\logs.
if not defined DOCULENS_VERIFY_CI pause
exit /b 1
