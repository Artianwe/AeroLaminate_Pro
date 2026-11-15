"""Automated checks for the Windows launchers (START/STOP_AEROLAMINATE.bat). Author: Anwesh Ajitabh Dash.

What runs where:
* Static cmd.exe lint - always (pure text analysis).
* PowerShell parse check of every embedded snippet - when Windows PowerShell or pwsh is available
  (set AEROLAMINATE_PWSH to an explicit executable path to choose one).
* Behavioural tests of the cross-platform snippets (HTTP probe, port check, build staleness) - same condition.
The cmd.exe control flow itself can only be exercised on Windows: see WINDOWS_VERIFICATION_CHECKLIST.md.
"""
import http.server
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BATS = [ROOT / "START_AEROLAMINATE.bat", ROOT / "STOP_AEROLAMINATE.bat"]
PS_RE = re.compile(r'^\s*powershell\b[^"]*-Command "(.*)"(?:\s*>nul.*)?\s*$', re.I)


def _lines(path):
    return path.read_bytes().decode("ascii").split("\r\n")


def _code(line):
    """Line without rem comments and with double-quoted strings blanked."""
    s = line.strip()
    if s.lower().startswith("rem ") or s.lower() == "rem" or s.startswith("::"):
        return ""
    return re.sub(r'"[^"]*"', '""', s)


def _snippets():
    out = []
    for b in BATS:
        for i, line in enumerate(_lines(b), 1):
            m = PS_RE.match(line)
            if m:
                out.append((b.name, i, m.group(1)))
    return out


# ----------------------------------------------------------------------------- static lint
@pytest.mark.parametrize("bat", BATS, ids=lambda p: p.name)
def test_crlf_and_ascii(bat):
    raw = bat.read_bytes()
    raw.decode("ascii")                                   # raises on non-ASCII
    assert b"\n" not in raw.replace(b"\r\n", b""), "LF-only line ending: cmd.exe mis-parses labels in LF files"
    assert raw.endswith(b"\r\n")


@pytest.mark.parametrize("bat", BATS, ids=lambda p: p.name)
def test_labels_resolve_and_unique(bat):
    lines = _lines(bat)
    labels = [l.strip()[1:].split()[0].lower() for l in lines if l.strip().startswith(":") and not l.strip().startswith("::")]
    assert len(labels) == len(set(labels)), "duplicate labels"
    for l in lines:
        c = _code(l)
        for kind, target in re.findall(r"\b(goto|call)\s+:([A-Za-z_][\w]*)", c, re.I):
            if target.lower() != "eof":
                assert target.lower() in labels, f"{kind} :{target} has no label"


@pytest.mark.parametrize("bat", BATS, ids=lambda p: p.name)
def test_no_parenthesised_blocks(bat):
    """%VAR% inside ( ... ) blocks is expanded once at parse time - the launcher avoids blocks entirely."""
    for i, l in enumerate(_lines(bat), 1):
        c = _code(l)
        assert c.count("(") == c.count(")"), f"line {i}: unbalanced parenthesis (block): {l.strip()}"
        assert not c.endswith("(") and not c.startswith(")"), f"line {i}: parenthesised block"


@pytest.mark.parametrize("bat", BATS, ids=lambda p: p.name)
def test_command_rules(bat):
    text = "\r\n".join(_lines(bat))
    assert re.search(r"^setlocal EnableExtensions DisableDelayedExpansion\s*$", text, re.M | re.I)
    for i, l in enumerate(_lines(bat), 1):
        c = _code(l).lower()
        if re.search(r"(^|&\s*|\|\s*)npm\b", c):
            pytest.fail(f"line {i}: npm must be invoked with 'call' (it is a .cmd script): {l.strip()}")
        assert not re.match(r"^timeout\b", c), f"line {i}: use ping for delays (timeout fails with redirected stdin)"
        assert not re.match(r"^cd /d\b", c), f"line {i}: use pushd (works from UNC paths)"


def test_powershell_snippets_static():
    sn = _snippets()
    assert len(sn) >= 4
    for name, i, code in sn:
        where = f"{name}:{i}"
        assert "%" not in code, f"{where}: %VAR% inside PowerShell code - pass values via $env: instead"
        assert '"' not in code, f"{where}: double quote inside the -Command string breaks cmd quoting"
        for tok in ("??", "?.", "&&", "||", "-NoProxy", "-SkipHttpErrorCheck"):
            assert tok not in code, f"{where}: '{tok}' is PowerShell 7-only; Windows ships PowerShell 5.1"


def test_start_launcher_structure():
    text = "\r\n".join(_lines(BATS[0]))
    for needle in ("127.0.0.1 --port %API_PORT%", "where npm", "struct.calcsize('P') == 8", "GetActiveTcpListeners",
                   "DefaultWebProxy = $null", "STOP_AEROLAMINATE.bat", "s.bind(('127.0.0.1', %API_PORT%))", "excludedportrange", 'start "" "%URL%"'):
        assert needle in text, needle
    code = " ".join(_code(l) for l in _lines(BATS[0])).lower()
    assert "netstat" not in code, "netstat state names are localised; use the .NET listener API"


# ----------------------------------------------------------------------------- PowerShell-backed checks
def _pwsh():
    exe = os.environ.get("AEROLAMINATE_PWSH") or shutil.which("powershell") or shutil.which("pwsh")
    return exe


needs_ps = pytest.mark.skipif(_pwsh() is None, reason="no PowerShell available (set AEROLAMINATE_PWSH)")


def _run(code, env):
    e = {**os.environ, **env}
    e.pop("HTTP_PROXY", None); e.pop("http_proxy", None)
    return subprocess.run([_pwsh(), "-NoProfile", "-NonInteractive", "-Command", code], env=e,
                          capture_output=True, text=True, timeout=60).returncode


def _snippet(contains):
    for _, _, code in _snippets():
        if contains in code:
            return code
    raise AssertionError(contains)


@needs_ps
def test_powershell_snippets_parse():
    for name, i, code in _snippets():
        check = ("$e=$null; [void][System.Management.Automation.Language.Parser]::ParseInput($env:SNIP, [ref]$null, [ref]$e); "
                 "if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 } else { exit 0 }")
        r = subprocess.run([_pwsh(), "-NoProfile", "-NonInteractive", "-Command", check], env={**os.environ, "SNIP": code},
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, f"{name}:{i} parse errors: {r.stdout}{r.stderr}"


@pytest.fixture()
def web_server():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/missing":
                self.send_response(404); self.end_headers(); return
            body = b"<html><title>AeroLaminate Pro</title></html>"
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


@needs_ps
def test_probe_snippet_behaviour(web_server):
    code = _snippet("Invoke-WebRequest")
    base = f"http://127.0.0.1:{web_server}/"
    assert _run(code, {"PROBE_URL": base, "PROBE_TEXT": ""}) == 0
    assert _run(code, {"PROBE_URL": base, "PROBE_TEXT": "AeroLaminate Pro"}) == 0
    assert _run(code, {"PROBE_URL": base, "PROBE_TEXT": "Something Else"}) == 1
    assert _run(code, {"PROBE_URL": base + "missing", "PROBE_TEXT": ""}) == 1
    assert _run(code, {"PROBE_URL": f"http://127.0.0.1:{_free_port()}/", "PROBE_TEXT": ""}) == 1


@needs_ps
def test_portbusy_snippet_behaviour():
    code = _snippet("GetActiveTcpListeners")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(1)
    try:
        assert _run(code, {"PORT_Q": str(s.getsockname()[1])}) == 0
    finally:
        s.close()
    assert _run(code, {"PORT_Q": str(_free_port())}) == 1


@needs_ps
def test_build_staleness_snippet_behaviour(tmp_path):
    code = _snippet("BUILD_ID")
    f = tmp_path / "front end (copy) & co"          # spaces, parentheses and & in the path
    (f / "src" / "app").mkdir(parents=True)
    for n in ("package.json", "next.config.mjs", "tailwind.config.ts", "src/app/page.tsx"):
        (f / n).write_text("x")
    env = {"FRONTEND": str(f)}
    assert _run(code, env) == 1                            # no build yet
    (f / ".next").mkdir()
    time.sleep(0.05)
    (f / ".next" / "BUILD_ID").write_text("id")
    assert _run(code, env) == 0                            # build newer than sources
    time.sleep(0.05)
    (f / "src" / "app" / "page.tsx").write_text("changed")
    assert _run(code, env) == 1                            # source edited after build
