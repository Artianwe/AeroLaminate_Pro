# AeroLaminate Pro — Windows Manual Verification Checklist

**Author, owner and maintainer:** Anwesh Ajitabh Dash

**Status: NOT YET EXECUTED.** None of the checks below has been run on Windows. The launchers were developed and checked on Linux
(static lint, PowerShell 7.4 parse and behaviour tests of the embedded snippets, and every non-cmd step run from a clean copy). The
cmd.exe control flow, Windows PowerShell 5.1 behaviour, `Get-NetTCPConnection`/`Get-CimInstance` (used by STOP) and window handling
have **never been executed**. Record the results in the table at the end and copy them into `VERIFICATION_REPORT.md`.

## Test machine record

| Item | Value |
|---|---|
| Windows edition / version / build (`winver`) | |
| System locale and display language | |
| Console host (Windows Console Host or Windows Terminal) | |
| Python (`py -3 --version`; 64-bit?) | |
| Node.js / npm (`node --version`, `npm --version`) | |
| PowerShell (`powershell -Command "$PSVersionTable.PSVersion"`) | |
| Repository path (note spaces, parentheses or non-ASCII characters) | |
| Corporate proxy / antivirus in use? | |
| Tester, date | |

## A. Automated checks on Windows (run first)

| # | Action | Expected |
|---|---|---|
| A1 | `cd backend` then `py -3 -m venv .venv` and `.venv\Scripts\python -m pip install -r requirements-dev.txt` | Installs without errors |
| A2 | `.venv\Scripts\python -m pytest -q` | All tests pass. On Windows, `test_launcher.py` also runs the PowerShell tests against **Windows PowerShell 5.1** (the version the launcher really uses), so 0 skipped is expected |
| A3 | `cd ..\frontend`, `npm ci`, `npm test`, `npx tsc --noEmit`, `npm run build` | 5 tests pass, no type errors, build succeeds |

## B. Launcher — first run and repeated runs

| # | Action | Expected |
|---|---|---|
| B1 | Fresh clone (no `backend\.venv`, no `frontend\node_modules`, no `frontend\.next`). Double-click `START_AEROLAMINATE.bat` | Prerequisite lines `[ok] Python …`, `[ok] Node.js …`; venv is created; pip and npm install; UI build runs; two new console windows open (*AeroLaminate Pro – API …* and *… Web UI …*); browser opens `http://127.0.0.1:3000/` and shows the workspace with status **SOLVED** |
| B2 | With the app open, run `backend\.venv\Scripts\python tools\smoke_test.py` | `18/18 checks passed`, exit code 0 |
| B3 | Double-click the launcher again while both services run | Prints `already running - opening the browser`; no new windows; no reinstall |
| B4 | Close both service windows. Double-click the launcher | No pip/npm install and no build (`up to date` lines); services start in under about 30 s |
| B5 | Edit any file under `frontend\src` (for example, add a blank line), then relaunch | `Building the web UI` runs once; the next relaunch does not rebuild |
| B6 | Close only the **API** window, then relaunch | `Web UI already running on port 3000 - reusing it`; only the API window opens; browser opens |
| B7 | Close only the **Web UI** window, then relaunch | `Analysis engine already running on port 8000 - reusing it`; only the UI window opens |

## C. Failure handling

| # | Action | Expected |
|---|---|---|
| C1 | Occupy port 3000 with another program (`py -3 -m http.server 3000` in a separate console), then launch | `[error] Port 3000 is used by another program …`; the window stays open (pause); nothing is killed |
| C2 | Same as C1 for port 8000 | `[error] Port 8000 is used by another program …` |
| C2b | If `netsh interface ipv4 show excludedportrange protocol=tcp` lists a range containing 8000 or 3000 (common with Hyper-V/WSL/Docker), launch | `[error] Port … cannot be opened on 127.0.0.1 …` with the netsh/winnat advice, instead of an engine window crashing with WinError 10013 |
| C3 | Temporarily rename the folder containing `node.exe` out of PATH (or use a console with a reduced PATH: `set PATH=C:\Windows\system32` and run the .bat from it) | `[error] Node.js was not found on PATH …` and pause |
| C4 | Same with Python removed from PATH (and the `py` launcher absent) | `[error] Python 3.10 or newer was not found …` |
| C5 | If available: 32-bit Python first on PATH | `[error] A 64-bit Python is required …` |
| C6 | Disconnect the network, delete `backend\.venv`, launch | pip fails → `[error] Python dependency installation failed …`; relaunch after reconnecting succeeds |
| C7 | Break the venv (rename `backend\.venv\pyvenv.cfg`), launch | `The existing backend\.venv is broken … recreating it`, then a normal start |
| C8 | Introduce a syntax error in `backend\app\main.py`, launch | API window shows a traceback; after about 3 min the launcher reports `Analysis engine: NOT responding`. Revert the change afterwards |

## D. Stop helper

| # | Action | Expected |
|---|---|---|
| D1 | With both services running, double-click `STOP_AEROLAMINATE.bat` | `[ok] Stopped the analysis engine on port 8000.` and `… web UI on port 3000.`; both ports become free (`netstat -ano | findstr :8000` empty) |
| D2 | Run STOP again | `[ok] No … was running …` for both |
| D3 | Run `py -3 -m http.server 8000` in a console, then STOP | `[warn] Port 8000 is used by a program that is not the AeroLaminate Pro analysis engine; it was left running.`; the http.server keeps running |
| D4 | Repeat D1 with **Windows Terminal** as the default terminal (Windows 11 setting) | Same as D1 (the processes are found by port and command line, not by window title); empty tabs may remain open |

## E. Environment variations

| # | Action | Expected |
|---|---|---|
| E1 | Copy the repository to a path with spaces, parentheses and `&` (for example `C:\Users\<you>\Desktop\Aero (copy) & test`) and run B1, D1 | Works identically |
| E2 | Run from a mapped network/UNC path (`\\server\share\…`) | `pushd` maps a temporary drive letter and startup works, or a clear error (record which) |
| E3 | Non-English Windows display language (for example German or French) | Port checks behave as in C1/C2 (they use .NET, not localised `netstat` text) |
| E4 | System proxy configured (Settings → Network → Proxy) | Probes reach 127.0.0.1 directly (the proxy is disabled for probes); startup completes |
| E5 | Windows Firewall prompt on first start | No prompt is expected (both servers bind to 127.0.0.1 only). Record whether one appears |

## F. Application smoke (manual, in the browser)

| # | Action | Expected |
|---|---|---|
| F1 | Visit every tab | Plots render; no "This view could not be rendered" messages |
| F2 | Select *CYCOM 5320-1 / T650-35* | Red message *Analysis blocked … ILLUSTRATIVE …*, no results shown; **Enable demonstration mode** shows results with red banners; **Turn off** blocks again |
| F3 | Select IM7/8552, click *Cure residual (177→21 °C)* | Error: `… has no value for 'alpha1' …` (no CTE is invented); results are not shown as current (STALE banner if earlier results exist) |
| F4 | Save the project, click New, then Open the saved file | Project restored |
| F5 | Report → browser print to PDF | Printable report, attribution to Anwesh Ajitabh Dash in the header and footer |
| F6 | PNG / SVG / CSV export on any plot | Files download and open |

## Results record

| Check | Pass / Fail | Notes (paste messages for failures) |
|---|---|---|
| A1–A3 | | |
| B1–B7 | | |
| C1–C8 | | |
| D1–D4 | | |
| E1–E5 | | |
| F1–F6 | | |
