@echo off
rem ===========================================================================
rem  AeroLaminate Pro - stop helper
rem  Author, owner and maintainer: Anwesh Ajitabh Dash
rem
rem  Stops only the AeroLaminate Pro servers started by START_AEROLAMINATE.bat:
rem   1. finds the process listening on port 8000 / 3000 (Get-NetTCPConnection),
rem   2. stops it ONLY if its command line identifies it as our server
rem      (uvicorn app.main:app / Next.js) - unrelated programs are never killed,
rem   3. closes leftover console windows by title (classic console host only;
rem      under Windows Terminal the emptied tabs can be closed by hand).
rem  Same implementation rules as START_AEROLAMINATE.bat (no blocks, CRLF, ASCII).
rem ===========================================================================
setlocal EnableExtensions DisableDelayedExpansion
where powershell >nul 2>nul
if errorlevel 1 goto :ps_err

set "STOP_PORT=8000"
set "STOP_SIG=*uvicorn*app.main:app*"
set "STOP_NAME=analysis engine"
call :stopport
set "STOP_PORT=3000"
set "STOP_SIG=*next*"
set "STOP_NAME=web UI"
call :stopport

taskkill /FI "WINDOWTITLE eq AeroLaminate Pro - API*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq AeroLaminate Pro - Web UI*" /T /F >nul 2>nul
echo Done.
ping -n 4 127.0.0.1 >nul
endlocal
exit /b 0

:stopport
rem  Exit codes from the PowerShell snippet: 0 stopped, 2 nothing listening, 3 foreign process (left alone), 4 error
powershell -NoProfile -NonInteractive -Command "$p = [int]$env:STOP_PORT; try { $c = @(Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction Stop) } catch { $c = @() }; if ($c.Count -eq 0) { exit 2 }; $rc = 0; foreach ($id in ($c | Select-Object -ExpandProperty OwningProcess -Unique)) { $pr = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $id); if ($pr -and $pr.CommandLine -like $env:STOP_SIG) { & taskkill.exe /PID $id /T /F | Out-Null; if ($LASTEXITCODE -ne 0) { $rc = 4 } } else { $rc = 3 } }; exit $rc"
if errorlevel 4 goto :stop_err
if errorlevel 3 goto :stop_foreign
if errorlevel 2 goto :stop_none
echo [ok] Stopped the %STOP_NAME% on port %STOP_PORT%.
exit /b 0
:stop_none
echo [ok] No %STOP_NAME% was running on port %STOP_PORT%.
exit /b 0
:stop_foreign
echo [warn] Port %STOP_PORT% is used by a program that is not the AeroLaminate Pro %STOP_NAME%; it was left running.
exit /b 0
:stop_err
echo [error] Could not stop the %STOP_NAME% on port %STOP_PORT% - close its console window manually.
exit /b 0

:ps_err
echo [error] Windows PowerShell was not found. Close the "AeroLaminate Pro" console windows manually.
pause
endlocal
exit /b 1
