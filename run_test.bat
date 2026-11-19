@echo off
cd /d "%~dp0"
echo Launching PDF Master Pro (Test Build)...
"C:\Users\A960585\p\Scripts\python.exe" "PDF editor tool.py"
if errorlevel 1 (
    echo.
    echo An error occurred while running the application.
    pause
)
