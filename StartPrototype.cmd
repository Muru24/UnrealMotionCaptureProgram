@echo off
setlocal
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Project virtual environment was not found. See README.md.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0LaunchPrototype.pyw"
