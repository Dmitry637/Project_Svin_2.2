@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
py main.py %*
set "APP_EXIT_CODE=%ERRORLEVEL%"
echo.
if "%APP_EXIT_CODE%"=="0" (echo Application finished successfully.) else (echo Application finished with error code %APP_EXIT_CODE%.)
echo.
pause
exit /b %APP_EXIT_CODE%
