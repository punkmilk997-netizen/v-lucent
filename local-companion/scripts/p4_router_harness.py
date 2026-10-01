"""P4 router harness — no provider API calls.
Mirrors live settings and asserts light / heavy / vision picks.
"""
from __future__ import annotations

# Live settings (keys redacted / unused)
SETTINGS = {
    "model_router": True,
    "groq_model": "openai/gpt-oss-20b",
    "heavy_model": "openai/gpt-oss-120b",
    "vision_model": "qwen/qwen3.8-27b",
    "tools_allow_shell": False,
}

KEYS = [
    "plan", "fix", "debug", "refactor", "implement", "architecture",
    "stack trace", "compile", "cargo ", "typescript", "python", "rustc",
    "```", "function ", "class ", "error:", "traceback", "step by step",
    "compare", "analyze", "write a", "build a", "design a",
]


def message_looks_complex(text: str) -> bool:
    lower = text.lower()
    if len(text) > 220:
        return True
    return any(k in lower for k in KEYS)


def resolve_chat(text: str, tools_path: bool = False) -> dict:
    light = SETTINGS["groq_model"].strip()
    heavy = SETTINGS["heavy_model"].strip()
    if not SETTINGS["model_router"] or not heavy:
        return {"tier": "light", "model": light, "reason": "router_off_or_heavy_unset"}
    if tools_path:
        return {"tier": "heavy", "model": heavy, "reason": "tools_path"}
    if message_looks_complex(text):
        return {"tier": "heavy", "model": heavy, "reason": "complex_message"}
    return {"tier": "light", "model": light, "reason": "simple_chat"}


def resolve_vision() -> dict:
    return {
        "tier": "vision",
        "model": SETTINGS["vision_model"],
        "reason": "vision_model_setting",
    }


CASES = [
    ("hey what's up?", False, "light", "openai/gpt-oss-20b"),
    ("please debug this rustc error and refactor", False, "heavy", "openai/gpt-oss-120b"),
    ("hi", True, "heavy", "openai/gpt-oss-120b"),
    ("a" * 221, False, "heavy", "openai/gpt-oss-120b"),
]

failed = 0
print("settings:", {k: v for k, v in SETTINGS.items()})
assert SETTINGS["tools_allow_shell"] is False

for text, tools_path, want_tier, want_model in CASES:
    got = resolve_chat(text, tools_path)
    ok = got["tier"] == want_tier and got["model"] == want_model
    status = "PASS" if ok else "FAIL"
    if not ok:
        failed += 1
    preview = text if len(text) <= 40 else text[:37] + "..."
    print(f"[{status}] chat tools_path={tools_path} text={preview!r} -> {got}")

vis = resolve_vision()
ok = vis["tier"] == "vision" and vis["model"] == "qwen/qwen3.8-27b"
print(f"[{'PASS' if ok else 'FAIL'}] vision -> {vis}")
if not ok:
    failed += 1

# gpt-oss only via settings: custom settings must not invent oss ids
custom_light = "vendor/other-8b"
custom_heavy = "vendor/other-70b"
SETTINGS["groq_model"] = custom_light
SETTINGS["heavy_model"] = custom_heavy
got = resolve_chat("hi")
ok = got["model"] == custom_light and "gpt-oss" not in got["model"]
print(f"[{'PASS' if ok else 'FAIL'}] custom light (no hardcoded gpt-oss) -> {got}")
if not ok:
    failed += 1

print("RESULT:", "PASS" if failed == 0 else f"FAIL ({failed})")
raise SystemExit(failed)
