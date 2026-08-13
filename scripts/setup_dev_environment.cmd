@echo off
setlocal
cd /d "%~dp0.."

echo AIMA_UGC development environment bootstrap
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_dev_environment.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
  echo AIMA_UGC environment setup failed with exit code %EXIT_CODE%.
) else (
  echo AIMA_UGC environment setup completed successfully.
)
echo.
pause
exit /b %EXIT_CODE%
