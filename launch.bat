@echo off
cd /d "%~dp0"

title TaikiTalki Launcher

:: ── Find Python (py launcher first) ───────────────────────────
set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY goto no_python
echo [OK] Using Python: %PY%
echo.

:: ── Check Firefox, install if missing ─────────────────────────
if exist "%ProgramFiles%\Mozilla Firefox\firefox.exe" goto firefox_ok
if exist "%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe" goto firefox_ok
echo Firefox not found. Downloading and installing...
powershell -Command "$u='https://download.mozilla.org/?product=firefox-latest'+[char]38+'os=win64'+[char]38+'lang=en-US'; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile \"$env:TEMP\firefox_installer.exe\"; Start-Process \"$env:TEMP\firefox_installer.exe\" -ArgumentList '-ms' -Wait"
echo Firefox installed.
:firefox_ok

:: ── Update ONLY events.json ───────────────────────────────────
echo Updating files from GitHub...
powershell -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/KawaiiIdolTaiki/TaikiTalki/main/events.json' -OutFile '%~dp0events.json'; Write-Host 'events.json updated.' } catch { Write-Host 'events.json: using local copy.' }"
powershell -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/KawaiiIdolTaiki/TaikiTalki/main/dumper.py' -OutFile '%~dp0dumper.py'; Write-Host 'dumper.py updated.' } catch { Write-Host 'dumper.py: using local copy.' }"
powershell -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/KawaiiIdolTaiki/TaikiTalki/main/taikitalki.py' -OutFile '%~dp0taikitalki.py'; Write-Host 'taikitalki.py updated.' } catch { Write-Host 'taikitalki.py: using local copy.' }"
echo.

:: ── Install requirements ──────────────────────────────────────
echo Checking requirements...
%PY% -m pip install -r "%~dp0requirements.txt" --quiet
echo.

:: ── Launch both, minimized ────────────────────────────────────
echo Launching...
start "Dumper" /min %PY% "%~dp0dumper.py"
start "TaikiTalki" /min %PY% "%~dp0taikitalki.py"

:: ── Close the launcher ────────────────────────────────────────
exit

:no_python
echo [ERROR] Python was not found.
echo Install from https://www.python.org/downloads/ and tick "Add Python to PATH", then retry.
echo.
pause
exit /b