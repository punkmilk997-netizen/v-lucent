"""P5 agency harness — mirrors Rust agency rules without needing the app running.
Asserts: no silent create, persist-shaped roundtrip, fire-once, cancel.
tools_allow_shell stays false.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

TOOLS_ALLOW_SHELL = False


class Agency:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"consent": False, "consent_at_ms": None, "items": [], "fire_log": []}

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def load(self):
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def set_consent(self, consent: bool, now: int):
        self.data["consent"] = consent
        if consent:
            self.data["consent_at_ms"] = now
        else:
            for it in self.data["items"]:
                if it["status"] == "pending":
                    it["status"] = "cancelled"
                    it["cancelled_ms"] = now
        self.save()

    def create(self, kind: str, title: str, message: str, fire_at_ms: int, now: int):
        if not self.data["consent"]:
            raise RuntimeError("agency consent required")
        item = {
            "id": f"{'r' if kind == 'reminder' else 'w'}{now}",
            "kind": kind,
            "title": title,
            "message": message or title,
            "fire_at_ms": fire_at_ms,
            "status": "pending",
            "created_ms": now,
            "fired_ms": None,
            "cancelled_ms": None,
        }
        self.data["items"].append(item)
        self.save()
        return item

    def tick(self, now: int):
        if not self.data["consent"]:
            return []
        fired = []
        for it in self.data["items"]:
            if it["status"] == "pending" and it["fire_at_ms"] <= now:
                it["status"] = "fired"
                it["fired_ms"] = now
                rec = {"id": it["id"], "title": it["title"], "message": it["message"], "fired_ms": now}
                fired.append(rec)
                self.data["fire_log"].append(rec)
        if fired:
            self.save()
        return fired

    def cancel(self, id_: str, now: int):
        for it in self.data["items"]:
            if it["id"] == id_:
                if it["status"] == "fired":
                    raise RuntimeError("cannot cancel already-fired")
                if it["status"] == "cancelled":
                    return "already cancelled"
                it["status"] = "cancelled"
                it["cancelled_ms"] = now
                self.save()
                return f"cancelled {id_}"
        raise RuntimeError("missing id")


failed = 0

def check(name: str, cond: bool, detail=""):
    global failed
    status = "PASS" if cond else "FAIL"
    if not cond:
        failed += 1
    print(f"[{status}] {name} {detail}")


assert TOOLS_ALLOW_SHELL is False
check("tools_allow_shell stays false", TOOLS_ALLOW_SHELL is False)

with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "agency.json"
    a = Agency(path)

    try:
        a.create("reminder", "x", "y", 100, now=1)
        check("create without consent blocked", False)
    except RuntimeError as e:
        check("create without consent blocked", "consent" in str(e).lower())

    a.set_consent(True, now=10)
    item = a.create("reminder", "hydrate", "drink", fire_at_ms=1000, now=10)
    a.load()
    check("persist consent+item", a.data["consent"] is True and len(a.data["items"]) == 1, path.name)

    fired = a.tick(500)
    check("not due yet", fired == [])

    fired = a.tick(1000)
    check("fire once", len(fired) == 1 and fired[0]["id"] == item["id"])

    fired2 = a.tick(2000)
    check("no re-fire", fired2 == [])

    w = a.create("watcher", "ci", "check", fire_at_ms=5000, now=20)
    msg = a.cancel(w["id"], now=21)
    check("cancel works", "cancelled" in msg)
    try:
        a.cancel(item["id"], now=22)
        check("cancel fired blocked", False)
    except RuntimeError as e:
        check("cancel fired blocked", "already-fired" in str(e))

    a.set_consent(False, now=30)
    pending = [i for i in a.data["items"] if i["status"] == "pending"]
    check("revoke cancels pending", pending == [])

print("RESULT:", "PASS" if failed == 0 else f"FAIL ({failed})")
raise SystemExit(failed)
