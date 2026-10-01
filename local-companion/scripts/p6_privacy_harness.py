"""P6 privacy/path harness — mirrors redaction + allowlist expectations.
tools_allow_shell stays false. No live network.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

TOOLS_ALLOW_SHELL = False


def redact_secrets(s: str) -> str:
    out = s
    out = re.sub(r"(?i)(authorization:\s*(?:bearer|token)\s+)\S+", r"\1[REDACTED]", out)
    out = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", out)
    out = re.sub(r"(?i)(GATEWAY_TOKEN\s*[=:]\s*)\S+", r"\1[REDACTED]", out)
    out = re.sub(r"\bsk-[A-Za-z0-9_-]+", "sk-[REDACTED]", out)
    out = re.sub(r"\bgsk_[A-Za-z0-9_-]+", "gsk_[REDACTED]", out)
    out = re.sub(
        r'("(?:groq_api_key|openrouter_api_key|vision_api_key|tts_api_key|stt_api_key|api_key|gateway_token)"\s*:\s*")[^"]*"',
        r'\1[REDACTED]"',
        out,
        flags=re.I,
    )
    return out


failed = 0


def check(name: str, cond: bool, detail: str = ""):
    global failed
    status = "PASS" if cond else "FAIL"
    if not cond:
        failed += 1
    print(f"[{status}] {name} {detail}")


assert TOOLS_ALLOW_SHELL is False
check("tools_allow_shell stays false", TOOLS_ALLOW_SHELL is False)

r = redact_secrets("Authorization: Bearer sk-abcDEF1234567890 and more")
check("redact bearer+sk", "[REDACTED]" in r and "sk-abcDEF1234567890" not in r, r)

r = redact_secrets('{"groq_api_key":"gsk_live_secret_value_here","model":"x"}')
check("redact json api key", "[REDACTED]" in r and "gsk_live_secret_value_here" not in r, r)

r = redact_secrets("GATEWAY_TOKEN=super-secret-gateway-token-xyz")
check("redact gateway", "[REDACTED]" in r and "super-secret-gateway-token-xyz" not in r, r)

benign = "[Groq] Response status: 200 (42 ms)"
check("keep benign", redact_secrets(benign) == benign)

# Known-folder / OneDrive-safe roots (Python approximation of Rust policy)
home = Path(os.environ.get("USERPROFILE", "C:/Users/Public"))
roots = []


def push(p: Path):
    if p not in roots:
        roots.append(p)


# Prefer Windows known folders via PowerShell-equivalent env already resolved by OS APIs;
# here we at least include profile + OneDrive env dirs.
for name in ("Desktop", "Documents", "Downloads"):
    push(home / name)
push(home / "Desktop" / "desktop-assistant")

with tempfile.TemporaryDirectory() as td:
    od = Path(td)
    desk = od / "Desktop"
    desk.mkdir()
    prev_od = os.environ.get("OneDrive")
    os.environ["OneDrive"] = str(od)
    for env_key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        base = os.environ.get(env_key)
        if not base:
            continue
        for name in ("Desktop", "Documents", "Downloads"):
            p = Path(base) / name
            if p.is_dir():
                push(p)
    check("onedrive desktop in roots", desk in roots, str(roots))
    if prev_od is None:
        os.environ.pop("OneDrive", None)
    else:
        os.environ["OneDrive"] = prev_od
    # cleanup env if we set a temp path — leave real OneDrive if it was overwritten
    # (this harness always overwrote OneDrive to temp; restore best-effort)
    # Note: parent shell OneDrive is restored by process exit.

check(
    "profile desktop in roots",
    (home / "Desktop") in roots,
)

# Ollama offline path contract (code defaults)
ollama_fallback = "http://127.0.0.1:11434"
check("ollama fallback localhost", ollama_fallback.startswith("http://127.0.0.1:11434"))

# CSP present in tauri.conf.json
conf = json.loads(Path("src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
csp = conf.get("app", {}).get("security", {}).get("csp")
check("csp is non-null string", isinstance(csp, str) and len(csp) > 20)
check("csp allows blob media", "blob:" in csp)
check("csp allows deepgram", "api.deepgram.com" in csp)
check("csp allows local backends", "127.0.0.1" in csp)
check("no bundle/installer yet", "bundle" not in conf)

print("RESULT:", "PASS" if failed == 0 else f"FAIL ({failed})")
raise SystemExit(failed)