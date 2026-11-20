"""OpenClaw gateway adapter (G7).

Interface discipline (mandate): use ONLY documented surfaces. Today that is
exactly one endpoint — `GET {gateway}/v1/models` — the same probe the deployed
office's `integrations.js` already relies on. Operations without a documented
gateway surface return `supported: False` explicitly; no endpoints or event
schemas are invented. Connectivity failures are honest offline results, never
simulated successes.
"""

import os
import time

import httpx

OPERATIONS_WITHOUT_DOCUMENTED_INTERFACE = (
    "session.status",
    "task.submit",
    "task.result",
    "task.cancel",
    "activity.observe",
    "native_agent.discover",
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class OpenClawGatewayAdapter:
    """G5 handler contract: invoke(operation, payload) -> dict."""

    provider_id = "openclaw_gateway"
    category = "agent_harness"
    implementation = "python"

    def __init__(
        self,
        gateway_url: str | None = None,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 2.5,
    ) -> None:
        self.gateway_url = (
            gateway_url or os.environ.get("OPENCLAW_GATEWAY_URL") or "http://127.0.0.1:18789"
        ).rstrip("/")
        self.token = token if token is not None else os.environ.get("OPENCLAW_GATEWAY_TOKEN")
        self.timeout = timeout
        self._transport = transport  # injectable MockTransport for contract tests

    def probe_models(self) -> dict:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        client_kwargs: dict = {"timeout": self.timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        try:
            with httpx.Client(**client_kwargs) as client:
                response = client.get(f"{self.gateway_url}/v1/models", headers=headers)
        except httpx.HTTPError as exc:
            return {"online": False, "auth": "n/a", "models": [], "error": type(exc).__name__}
        if response.status_code == 401:
            return {"online": True, "auth": "rejected", "models": []}
        if response.status_code != 200:
            return {
                "online": True,
                "auth": "n/a",
                "models": [],
                "error": f"HTTP {response.status_code}",
            }
        try:
            body = response.json()
            models = [m["id"] for m in body.get("data", []) if isinstance(m, dict) and "id" in m]
        except ValueError:
            return {"online": True, "auth": "ok", "models": [], "error": "non-JSON body"}
        return {"online": True, "auth": "ok", "models": models}

    def invoke(self, operation: str, payload: dict | None = None) -> dict:
        _ = payload
        if operation in ("gateway.health", "agent.discovery"):
            probe = self.probe_models()
            if operation == "gateway.health":
                return {"supported": True, "kind": "health", "checked_at": _now(), "result": probe}
            if not probe["online"]:
                return {
                    "supported": True,
                    "kind": "discovery",
                    "checked_at": _now(),
                    "result": {
                        "gateway_models": [],
                        "native_agent_discovery": "unavailable: gateway offline",
                    },
                }
            return {
                "supported": True,
                "kind": "discovery",
                "checked_at": _now(),
                "result": {
                    "gateway_models": probe["models"],
                    "native_agent_discovery": (
                        "unsupported: only /v1/models is documented at this gateway surface"
                    ),
                },
            }
        if operation in OPERATIONS_WITHOUT_DOCUMENTED_INTERFACE:
            return {
                "supported": False,
                "operation": operation,
                "reason": "no documented gateway interface for this operation",
            }
        return {"supported": False, "operation": operation, "reason": "unknown operation"}
