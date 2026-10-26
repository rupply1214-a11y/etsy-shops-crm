@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw app.py & exit /b 0)
python app.py
if errorlevel 1 pause
