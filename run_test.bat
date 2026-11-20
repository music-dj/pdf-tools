@echo off
cd /d "%~dp0"
echo ========================================================
echo  Launching PDF Master Pro V3.3.0 (Test Version)
echo ========================================================
echo.

python "PDF editor tool.py"
if errorlevel 1 (
    echo.
    echo Trying with py launcher...
    py "PDF editor tool.py"
)

if errorlevel 1 (
    echo.
    echo [ERROR] Could not start the application. Please check your Python installation.
    pause
)
