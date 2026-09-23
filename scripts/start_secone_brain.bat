@echo off
setlocal

rem Meant to be registered as a Windows Task Scheduler task that fires "at
rem log on" (see README.md, "Auto-start on boot (Windows)" section) - this
rem is what actually runs each time you turn your computer on and log in.
rem Assumes it lives in <repo>\scripts\ - the cd below walks up from there.
cd /d "%~dp0.."

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found - run the Setup steps in README.md first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

if not exist "credentials.json" (
    echo credentials.json is missing - see README.md, "Calendar"/"Gmail" sections, to get it.
    echo Starting the server without Calendar/Gmail access for now...
    goto :start_server
)

if not exist "token.json" (
    echo No Google token yet - opening your browser once to connect Calendar + Gmail...
    python scripts\google_auth.py
    if errorlevel 1 (
        echo Google setup didn't finish - starting the server anyway. Run
        echo "python scripts\google_auth.py" by hand later to try again.
    )
)

:start_server
echo.
echo Starting Secone Brain on http://0.0.0.0:8000 - reachable from this PC
echo and, per the README's phone section, from your phone on the same
echo trusted Wi-Fi network. Close this window to stop the server.
echo.
uvicorn app.main:app --host 0.0.0.0

echo.
echo Server stopped.
pause
