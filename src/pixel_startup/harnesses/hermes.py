"""Hermes harness adapter (G8).

Interface: the filesystem Hermes itself maintains — the same two source-of-truth
files the deployed office's `integrations.js` reads. No private imports, nothing
routed through OpenClaw. Operations without a documented programmatic interface
return `supported: false` explicitly.
"""

import json
import os
from pathlib import Path

UNSUPPORTED_OPERATIONS = (
    "task.submit",
    "task.result",
    "task.cancel",
    "activity.observe",
)


def _pid_alive(pid: object) -> bool:
    try:
        os.kill(int(str(pid)), 0)
        return True
    except (OverflowError, ValueError, TypeError):
        return False
    except PermissionError:
        return True  # foreign process we cannot signal = alive
    except OSError:
        return False


class HermesHomeAdapter:
    """G5 handler contract: invoke(operation, payload) -> dict."""

    provider_id = "hermes_home"
    category = "agent_harness"
    implementation = "python"

    def __init__(self, hermes_home: str | None = None, liveness_fn=None) -> None:
        self.home = Path(hermes_home or os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
        self._alive = liveness_fn or _pid_alive

    def _read_json(self, relpath: str):
        path = self.home / relpath
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def probe(self) -> dict:
        sessions_file = self._read_json("runtime/active_sessions.json")
        gateway_file = self._read_json("gateway_state.json")
        entries = sessions_file.get("entries", []) if isinstance(sessions_file, dict) else []
        live_sessions = [
            {
                "session_id": e.get("session_id"),
                "surface": e.get("surface"),
                "pid": e.get("pid"),
                "started_at": e.get("started_at"),
            }
            for e in entries
            if isinstance(e, dict) and self._alive(e.get("pid"))
        ]
        gateway_running = bool(
            gateway_file
            and gateway_file.get("gateway_state") == "running"
            and self._alive(gateway_file.get("pid"))
        )
        platforms = [
            name
            for name, p in (gateway_file or {}).get("platforms", {}).items()
            if isinstance(p, dict) and p.get("state") == "connected"
        ]
        return {
            "home": str(self.home),
            "online": gateway_running or bool(live_sessions),
            "gateway": {
                "state": "running" if gateway_running else "offline",
                "pid": gateway_file.get("pid") if gateway_file else None,
                "active_agents": (gateway_file or {}).get("active_agents", 0),
            },
            "platforms": platforms,
            "sessions": live_sessions,
            "profiles": self.profiles(),
        }

    def profiles(self) -> list[str]:
        profiles_dir = self.home / "profiles"
        names = ["default"]
        if profiles_dir.is_dir():
            names += sorted(p.name for p in profiles_dir.iterdir() if p.is_dir())
        return names

    def invoke(self, operation: str, payload: dict | None = None) -> dict:
        _ = payload
        if operation in ("gateway.health", "session.status"):
            return {
                "supported": True,
                "kind": "health" if operation == "gateway.health" else "sessions",
                "result": self.probe(),
            }
        if operation in ("profile.discovery", "native_agent.discover"):
            probe = self.probe()
            return {
                "supported": True,
                "kind": "discovery",
                "result": {
                    "profiles": probe["profiles"],
                    "live_sessions": probe["sessions"],
                    "bindings": "employee binding is G9 (runtime identity binding), not yet wired",
                },
            }
        if operation in UNSUPPORTED_OPERATIONS:
            return {
                "supported": False,
                "operation": operation,
                "reason": "no programmatic task interface; Hermes uses the office REST API",
            }
        return {"supported": False, "operation": operation, "reason": "unknown operation"}
