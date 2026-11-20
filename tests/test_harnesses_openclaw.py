"""G7 OpenClaw adapter: contract tests against a mock gateway; live rows BLOCKED."""

import anyio
import httpx
import pytest

from pixel_startup.config import Settings
from pixel_startup.harnesses.openclaw import (
    OPERATIONS_WITHOUT_DOCUMENTED_INTERFACE,
    OpenClawGatewayAdapter,
)
from pixel_startup.main import create_app
from pixel_startup.providers.registry import ProviderError, ProviderState


def _make(offline: bool = False, token: str | None = None) -> httpx.MockTransport:
    def mock(request: httpx.Request) -> httpx.Response:
        if offline:
            raise httpx.ConnectError("connection refused", request=request)
        if token is not None and request.headers.get("authorization") != f"Bearer {token}":
            return httpx.Response(401, json={"error": "bad token"})
        return httpx.Response(200, json={"data": [{"id": "model.one"}, {"id": "model.two"}]})

    return httpx.MockTransport(mock)


def _adapter_with(
    transport: httpx.MockTransport, token: str | None = None
) -> OpenClawGatewayAdapter:
    return OpenClawGatewayAdapter(
        gateway_url="http://gw.test", token=token, transport=transport, timeout=0.5
    )


def test_health_online_lists_models() -> None:
    adapter = _adapter_with(_make(token="tok"), token="tok")
    result = adapter.invoke("gateway.health")
    assert result["supported"] is True and result["kind"] == "health"
    assert result["result"]["online"] is True
    assert result["result"]["models"] == ["model.one", "model.two"]
    assert result["result"]["auth"] == "ok"


def test_auth_rejected_is_honest() -> None:
    adapter = _adapter_with(_make(token="tok"), token="wrong")
    probe = adapter.invoke("gateway.health")["result"]
    assert probe["online"] is True and probe["auth"] == "rejected"


def test_offline_is_never_faked() -> None:
    adapter = _adapter_with(_make(offline=True))
    result = adapter.invoke("gateway.health")
    assert result["supported"] is True
    assert result["result"]["online"] is False
    assert "error" in result["result"]
    # discovery on an offline gateway is explicitly unavailable, not fabricated
    discovery = adapter.invoke("agent.discovery")["result"]
    assert discovery["gateway_models"] == []
    assert "unavailable: gateway offline" in discovery["native_agent_discovery"]


def test_undocumented_operations_never_call_the_wire() -> None:
    calls = {"n": 0}

    def mock(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"data": []})

    adapter = _adapter_with(httpx.MockTransport(mock))
    for op in OPERATIONS_WITHOUT_DOCUMENTED_INTERFACE:
        result = adapter.invoke(op)
        assert result == {
            "supported": False,
            "operation": op,
            "reason": "no documented gateway interface for this operation",
        }
    assert calls["n"] == 0  # no wire traffic for unsupported operations


def test_unknown_operation_explicit() -> None:
    adapter = _adapter_with(_make())
    result = adapter.invoke("make.coffee")
    assert result["supported"] is False and result["reason"] == "unknown operation"


def _promote(registry, pid):
    registry.transition(pid, ProviderState.CANDIDATE)


def test_lifespan_registers_openclaw_candidate(tmp_path) -> None:
    async def drive() -> None:
        app = create_app(Settings(pixel_data_dir=str(tmp_path / "d")))
        async with app.router.lifespan_context(app):
            registry = app.state.container.registry
            reg = registry.get("openclaw_gateway")
            assert (
                reg.state is ProviderState.CANDIDATE
            )  # live qualification BLOCKED -> not qualified
            assert reg.category.value == "agent_harness"
            assert reg.implementation == "python"
            # no ACTIVE agent harness exists yet: selection is honestly empty
            with pytest.raises(ProviderError):
                registry.select(reg.category)
        assert app.state.container.shutdowns == 1

    anyio.run(drive)
