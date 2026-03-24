@echo off
setlocal

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-manifold.ps1"
set "exit_code=%ERRORLEVEL%"

if not "%exit_code%"=="0" (
  echo.
  echo Manifold exited with code %exit_code%.
  pause
)

exit /b %exit_code%
