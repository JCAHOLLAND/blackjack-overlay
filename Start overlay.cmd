@echo off
cd /d "%~dp0"
py -3 -c "import tkinter" >nul 2>&1
if not errorlevel 1 (
    py -3 gui.py
    goto end
)
python -c "import tkinter" >nul 2>&1
if not errorlevel 1 (
    python gui.py
    goto end
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" gui.py
    goto end
)
echo Install Python with Tkinter to run the overlay.
pause
exit /b 1
:end
if errorlevel 1 pause
