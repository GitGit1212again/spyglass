@echo off
rem Starts Spyglass (closes itself when the page closes) and opens it in the browser.
rem First run only: creates the private .venv and installs the tools from requirements.txt.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto start

echo Setting up Spyglass for the first time. This downloads the tools and takes a few minutes.
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m venv .venv) else (python -m venv .venv)
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Could not create the private Python folder. Install Python 3.10 or newer from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH", then run this again.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo The install did not finish. Check your internet connection, then run this again.
  rmdir /s /q ".venv"
  pause
  exit /b 1
)

:start
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0server.py" --open
