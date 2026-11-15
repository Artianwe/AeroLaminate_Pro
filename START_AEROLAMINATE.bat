@echo off
rem ===========================================================================
rem  AeroLaminate Pro - Windows launcher
rem  Author, owner and maintainer: Anwesh Ajitabh Dash
rem
rem  Double-click to: check prerequisites, create/reuse the Python virtual
rem  environment, install missing dependencies, build the web UI when its
rem  sources changed, start the FastAPI engine (port 8000) and the Next.js UI
rem  (port 3000) in their own console windows, wait for both, and open the
rem  browser. Safe to run repeatedly: services already running are reused.
rem
rem  To stop: close the two windows titled "AeroLaminate Pro - ..."
rem  (or press Ctrl+C in each), or run STOP_AEROLAMINATE.bat.
rem  Requires: Windows 10/11, 64-bit Python 3.10+, Node.js 18.18+ (with npm),
rem  Windows PowerShell 5.1 (built in). No Docker or WSL.
rem
rem  Implementation rules (checked by backend/tests/test_launcher.py):
rem   - no parenthesised blocks: cmd expands %VAR% inside a block at parse
rem     time, so control flow uses goto and "if errorlevel" only;
rem   - npm is always invoked with "call" (it is a .cmd script);
rem   - PowerShell snippets read paths/URLs from environment variables only
rem     (no %VAR% inside PowerShell code) and use Windows PowerShell 5.1 syntax;
rem   - delays use ping, not timeout (timeout fails with redirected input);
rem   - CRLF line endings, ASCII only.
rem ===========================================================================
setlocal EnableExtensions DisableDelayedExpansion
title AeroLaminate Pro - launcher
rem pushd (not cd /d) also works from a UNC path by mapping a temporary drive
pushd "%~dp0" 2>nul
if errorlevel 1 goto :root_err
set "ROOT=%CD%\"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "VENV=%BACKEND%\.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "API_PORT=8000"
set "WEB_PORT=3000"
set "URL=http://127.0.0.1:%WEB_PORT%/"
set "API_URL=http://127.0.0.1:%API_PORT%/api/health"
set "NEXT_TELEMETRY_DISABLED=1"
set "API_RUNNING="
set "WEB_RUNNING="

echo.
echo   AeroLaminate Pro  -  composite laminate analysis workspace
echo   Author, owner and maintainer: Anwesh Ajitabh Dash
echo   -----------------------------------------------------------
echo.

rem ---------------------------------------------------------------- PowerShell (used for HTTP probes and port checks)
where powershell >nul 2>nul
if errorlevel 1 goto :ps_err

rem ---------------------------------------------------------------- already running?
call :probe "%URL%api/health" ""
if "%PROBE%"=="1" goto :already

rem ---------------------------------------------------------------- Python
set "PYCMD="
where py >nul 2>nul && py -3 -c "import sys" >nul 2>nul && set "PYCMD=py -3"
if defined PYCMD goto :pyfound
where python >nul 2>nul && python -c "import sys" >nul 2>nul && set "PYCMD=python"
if defined PYCMD goto :pyfound
echo [error] Python 3.10 or newer was not found on PATH.
echo         Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
goto :fail
:pyfound
%PYCMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if not errorlevel 1 goto :pyver_ok
echo [error] Python 3.10 or newer is required. Found:
%PYCMD% --version
goto :fail
:pyver_ok
%PYCMD% -c "import struct, sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)"
if not errorlevel 1 goto :pyok
echo [error] A 64-bit Python is required (SciPy publishes no 32-bit Windows wheels for current releases).
goto :fail
:pyok
for /f "delims=" %%v in ('%PYCMD% --version 2^>^&1') do echo [ok] %%v

rem ---------------------------------------------------------------- Node.js and npm
where node >nul 2>nul
if not errorlevel 1 goto :nodefound
echo [error] Node.js was not found on PATH. Install the LTS release from https://nodejs.org/
goto :fail
:nodefound
rem Next.js 15 supports Node ^18.18 or ^19.8 or >= 20
node -e "const [a,b]=process.versions.node.split('.').map(Number);process.exit((a===18&&b>=18)||(a===19&&b>=8)||a>=20?0:1)"
if not errorlevel 1 goto :nodeok
echo [error] Node.js 18.18 or newer is required. Found:
node --version
goto :fail
:nodeok
for /f "delims=" %%v in ('node --version') do echo [ok] Node.js %%v
where npm >nul 2>nul
if not errorlevel 1 goto :npmok
echo [error] npm was not found on PATH. Reinstall Node.js with the npm component.
goto :fail
:npmok

rem ---------------------------------------------------------------- ports (locale-independent check, IPv4 and IPv6)
call :portbusy %API_PORT%
if "%BUSY%"=="0" goto :apiport_free
call :probe "%API_URL%" ""
if "%PROBE%"=="1" goto :apiport_reuse
echo [error] Port %API_PORT% is used by another program. Close it, or run STOP_AEROLAMINATE.bat, and retry.
goto :fail
:apiport_reuse
echo [ok] Analysis engine already running on port %API_PORT% - reusing it.
set "API_RUNNING=1"
:apiport_free
call :portbusy %WEB_PORT%
if "%BUSY%"=="0" goto :ports_ok
call :probe "%URL%" "AeroLaminate Pro"
if "%PROBE%"=="1" goto :webport_reuse
echo [error] Port %WEB_PORT% is used by another program. Close it, or run STOP_AEROLAMINATE.bat, and retry.
goto :fail
:webport_reuse
echo [ok] Web UI already running on port %WEB_PORT% - reusing it.
set "WEB_RUNNING=1"
:ports_ok

rem ---------------------------------------------------------------- Python environment
if not exist "%VPY%" goto :venv_create
"%VPY%" -c "import sys" >nul 2>nul
if not errorlevel 1 goto :venv_ok
echo [..] The existing backend\.venv is broken (e.g. after a Python upgrade) - recreating it
rmdir /s /q "%VENV%"
:venv_create
echo [..] Creating Python virtual environment in backend\.venv
%PYCMD% -m venv "%VENV%"
if errorlevel 1 goto :venv_err
:venv_ok
fc /b "%BACKEND%\requirements.txt" "%VENV%\requirements.stamp" >nul 2>nul
if not errorlevel 1 goto :pydeps_check
:pydeps_install
echo [..] Installing Python dependencies - first run can take a few minutes
"%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip
"%VPY%" -m pip install --disable-pip-version-check -r "%BACKEND%\requirements.txt"
if errorlevel 1 goto :pip_err
copy /y "%BACKEND%\requirements.txt" "%VENV%\requirements.stamp" >nul
:pydeps_check
"%VPY%" -c "import numpy, scipy, fastapi, uvicorn, pydantic" >nul 2>nul
if not errorlevel 1 goto :pydeps_ok
if exist "%VENV%\repair.stamp" goto :pip_err
echo [..] Python dependencies incomplete - repairing
echo repair> "%VENV%\repair.stamp"
goto :pydeps_install
:pydeps_ok
del /q "%VENV%\repair.stamp" >nul 2>nul
echo [ok] Python dependencies ready

rem ---------------------------------------------------------------- Node dependencies and build (skipped while the UI is running)
if defined WEB_RUNNING goto :build_ok
if not exist "%FRONTEND%\node_modules\next\package.json" goto :npm_install
fc /b "%FRONTEND%\package-lock.json" "%FRONTEND%\node_modules\.lock.stamp" >nul 2>nul
if errorlevel 1 goto :npm_install
echo [ok] Web UI dependencies up to date
goto :npm_ok
:npm_install
echo [..] Installing web UI dependencies - first run can take a few minutes
pushd "%FRONTEND%"
if exist package-lock.json goto :npm_ci
call npm install --no-audit --no-fund
goto :npm_after
:npm_ci
call npm ci --no-audit --no-fund
:npm_after
if errorlevel 1 goto :npm_err
popd
copy /y "%FRONTEND%\package-lock.json" "%FRONTEND%\node_modules\.lock.stamp" >nul
:npm_ok
powershell -NoProfile -NonInteractive -Command "$f=$env:FRONTEND; $b=Join-Path $f '.next\BUILD_ID'; if(-not (Test-Path -LiteralPath $b)){exit 1}; $t=(Get-Item -LiteralPath $b).LastWriteTime; $src=@(Get-ChildItem -LiteralPath (Join-Path $f 'src') -Recurse -File) + @(Get-Item -LiteralPath (Join-Path $f 'package.json'),(Join-Path $f 'next.config.mjs'),(Join-Path $f 'tailwind.config.ts')); if($src | Where-Object { $_.LastWriteTime -gt $t }){exit 1}; exit 0" >nul 2>nul
if errorlevel 1 goto :build
echo [ok] Web UI build up to date
goto :build_ok
:build
echo [..] Building the web UI - about a minute
pushd "%FRONTEND%"
call npm run build
if errorlevel 1 goto :build_err
popd
:build_ok

rem ---------------------------------------------------------------- can the ports be bound? (Hyper-V/WSL/Docker reserve port ranges on Windows;
rem  a reserved port is not "listening", so the check above passes, yet the server would fail with WinError 10013)
if defined API_RUNNING goto :bind_web
"%VPY%" -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', %API_PORT%)); s.close()" >nul 2>nul
if errorlevel 1 goto :bind_err_api
:bind_web
if defined WEB_RUNNING goto :bind_ok
"%VPY%" -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', %WEB_PORT%)); s.close()" >nul 2>nul
if errorlevel 1 goto :bind_err_web
:bind_ok

rem ---------------------------------------------------------------- start servers
if defined API_RUNNING goto :start_web
echo [..] Starting analysis engine on http://127.0.0.1:%API_PORT%
start "AeroLaminate Pro - API port %API_PORT% - close to stop" /D "%BACKEND%" cmd /k ""%VPY%" -m uvicorn app.main:app --host 127.0.0.1 --port %API_PORT%"
:start_web
if defined WEB_RUNNING goto :wait_start
echo [..] Starting web UI on %URL%
start "AeroLaminate Pro - Web UI port %WEB_PORT% - close to stop" /D "%FRONTEND%" cmd /k "npm run start"

rem ---------------------------------------------------------------- wait for both (the UI proxies /api to the engine)
:wait_start
set /a TRIES=0
:wait
set /a TRIES+=1
call :probe "%URL%api/health" ""
if "%PROBE%"=="1" goto :ready
if %TRIES% GEQ 90 goto :timeout
set /a MOD=TRIES %% 15
if "%MOD%"=="0" echo [..] still waiting for the services - %TRIES% s
ping -n 2 127.0.0.1 >nul
goto :wait

:ready
echo [ok] Both services are up.
start "" "%URL%"
echo.
echo   AeroLaminate Pro is running at %URL%
echo   To stop it, close the two "AeroLaminate Pro" console windows
echo   or run STOP_AEROLAMINATE.bat. This launcher window can be closed.
echo.
goto :done

:already
echo [ok] AeroLaminate Pro is already running - opening the browser.
start "" "%URL%"
goto :done

rem ---------------------------------------------------------------- errors
:root_err
echo [error] Cannot change to the launcher folder "%~dp0".
goto :fail
:ps_err
echo [error] Windows PowerShell (powershell.exe) was not found; it is required for the startup checks.
goto :fail
:bind_err_api
set "BAD_PORT=%API_PORT%"
goto :bind_err
:bind_err_web
set "BAD_PORT=%WEB_PORT%"
:bind_err
echo [error] Port %BAD_PORT% cannot be opened on 127.0.0.1 although no program is listening on it.
echo         Windows has most likely reserved it for Hyper-V, WSL or Docker. To check, run:
echo             netsh interface ipv4 show excludedportrange protocol=tcp
echo         If %BAD_PORT% lies inside a listed range, restart Windows (the ranges change at boot)
echo         or, as administrator: net stop winnat  then  net start winnat  and run the launcher again.
goto :fail
:venv_err
echo [error] Could not create the Python virtual environment in backend\.venv
goto :fail
:pip_err
echo [error] Python dependency installation failed. Check the internet connection or proxy
echo         settings, then run the launcher again. Deleting backend\.venv forces a clean install.
goto :fail
:npm_err
popd
echo [error] npm install failed. Check the internet connection or proxy settings and retry.
echo         Deleting frontend\node_modules forces a clean install.
goto :fail
:build_err
popd
echo [error] The web UI build failed - see the messages above.
goto :fail
:timeout
echo [error] The services did not respond within about 3 minutes.
call :probe "%API_URL%" ""
if "%PROBE%"=="1" echo         Analysis engine: responding on port %API_PORT%.
if "%PROBE%"=="0" echo         Analysis engine: NOT responding - read the "AeroLaminate Pro - API" window.
call :probe "%URL%" "AeroLaminate Pro"
if "%PROBE%"=="1" echo         Web UI: responding on port %WEB_PORT%.
if "%PROBE%"=="0" echo         Web UI: NOT responding - read the "AeroLaminate Pro - Web UI" window.
echo         Run STOP_AEROLAMINATE.bat before retrying.
goto :fail

rem ===========================================================================
:probe
rem  %1 URL, %2 optional text the response body must contain. Sets PROBE=1 on HTTP 200 (+ text).
rem  The system proxy is disabled for the request so 127.0.0.1 is never sent to a corporate proxy.
set "PROBE=0"
set "PROBE_URL=%~1"
set "PROBE_TEXT=%~2"
powershell -NoProfile -NonInteractive -Command "[System.Net.WebRequest]::DefaultWebProxy = $null; try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri $env:PROBE_URL; if ($r.StatusCode -ne 200) { exit 1 }; if ($env:PROBE_TEXT -and ($r.Content -notlike ('*' + $env:PROBE_TEXT + '*'))) { exit 1 }; exit 0 } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 set "PROBE=1"
exit /b 0

:portbusy
rem  %1 port. Sets BUSY=1 if any process listens on it (IPv4 or IPv6). Uses .NET, so it does not depend
rem  on the localised state names printed by netstat.
set "BUSY=0"
set "PORT_Q=%~1"
powershell -NoProfile -NonInteractive -Command "$p = [int]$env:PORT_Q; $l = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -eq $p }; if ($l) { exit 0 } else { exit 1 }" >nul 2>nul
if not errorlevel 1 set "BUSY=1"
exit /b 0

:fail
echo.
echo   Startup did not complete. Fix the problem above and double-click the launcher again.
echo.
pause
popd
endlocal
exit /b 1

:done
ping -n 6 127.0.0.1 >nul
popd
endlocal
exit /b 0
