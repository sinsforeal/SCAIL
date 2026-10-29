"""HTTP client for an arm's control API (contract: Arm control API). 127.0.0.1 only."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class ArmError(RuntimeError):
    def __init__(self, status, body, path=""):
        self.status, self.body, self.path = status, body, path
        super().__init__(f"arm {path} -> {status}: {str(body)[:300]}")

    @property
    def budget(self) -> bool:
        return self.status == 402 or "budget_exhausted" in str(self.body)


class Arm:
    def __init__(self, port: int, timeout: float = 7200):  # P advances run long (cl1_p_tomoe paused at 1800 s, 10-22)
        self.base = f"http://127.0.0.1:{port}"
        self.port = port
        self.timeout = timeout

    def _req(self, method, path, body=None, timeout=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raise ArmError(e.code, e.read().decode("utf-8", "replace"), path)
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            raise ArmError(0, f"transport: {e}", path)
        return json.loads(raw) if raw else {}

    def up(self) -> bool:
        try:
            self._req("GET", "/control/state", timeout=3)
            return True
        except ArmError:
            return False

    def start(self, run_id, character, lang, clock_start, timeout=None, arm_variant="", seed=0, extra=None):
        body = {"run_id": run_id, "character": character, "lang": lang, "clock_start": clock_start}
        if arm_variant:
            # grounding test arms (tk-6r3): "own_day" or "absence"; seed keys the sick-day draw of own_day
            body.update({"arm_variant": arm_variant, "seed": int(seed or 0)})
        body.update(extra or {})  # a run's other minds: role, peer_key, peer_contacts (tk-1pl)
        return self._req("POST", "/control/start", body, timeout=timeout)

    def advance(self, to: str) -> list:
        return self.advance_full(to).get("outputs", [])

    def advance_full(self, to: str) -> dict:
        """outputs plus, from an arm that has them, peer_out (what she wrote to another mind) and place."""
        return self._req("POST", "/control/advance", {"to": to})

    def peer_in(self, messages: list):
        return self._req("POST", "/control/peer_in", {"messages": messages})

    def send(self, text: str, ts: str):
        return self._req("POST", "/control/send", {"text": text, "ts": ts})

    def env(self, events: list):
        return self._req("POST", "/control/env", {"events": events})

    def snapshot(self, name: str):
        return self._req("POST", "/control/snapshot", {"name": name})

    def restore(self, name: str):
        return self._req("POST", "/control/restore", {"name": name})

    def inject(self, target: str, value):
        return self._req("POST", "/control/inject", {"target": target, "value": value})

    def trace(self, output_id: str) -> dict:
        return self._req("GET", f"/control/trace/{output_id}")

    def state(self) -> dict:
        return self._req("GET", "/control/state")

    def stop(self):
        try:
            return self._req("POST", "/control/stop", {}, timeout=30)
        except ArmError:
            return {}
