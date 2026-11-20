"""G5 provider registry: explicit promotion, deterministic selection, no fallback."""

import importlib.util
import json
from pathlib import Path

import anyio
import httpx
import pytest

from pixel_startup.config import Settings
from pixel_startup.main import create_app
from pixel_startup.providers.registry import (
    ProviderCategory,
    ProviderError,
    ProviderRegistration,
    ProviderRegistry,
    ProviderState,
)

ROOT = Path(__file__).resolve().parent.parent


class OkProvider:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, operation: str, payload: dict) -> dict:
        self.calls += 1
        return {"ok": True, "operation": operation}


class DenyProvider:
    calls = 0

    def invoke(self, operation: str, payload: dict) -> dict:
        type(self).calls += 1
        raise PermissionError("authorization failure")


def _reg(
    pid: str,
    cat: ProviderCategory = ProviderCategory.AGENT_DISCOVERY,
    priority: int = 0,
    handler: object = None,
) -> ProviderRegistration:
    return ProviderRegistration(
        provider_id=pid,
        category=cat,
        implementation="python",
        capabilities=["cap.test"],
        priority=priority,
        handler=handler,
    )


def _load_subset_check():
    spec = importlib.util.spec_from_file_location(
        "g3subset", ROOT / "tests" / "contracts" / "validate_contracts.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check


def test_registration_never_auto_promotes() -> None:
    registry = ProviderRegistry()
    reg = registry.register(_reg("p1"))
    assert reg.state is ProviderState.REGISTERED
    with pytest.raises(ProviderError, match="no active provider"):
        registry.select(ProviderCategory.AGENT_DISCOVERY)


def test_duplicate_registration_rejected() -> None:
    registry = ProviderRegistry()
    registry.register(_reg("p1"))
    with pytest.raises(ProviderError, match="already registered"):
        registry.register(_reg("p1"))


def test_explicit_promotion_and_illegal_jumps() -> None:
    registry = ProviderRegistry()
    registry.register(_reg("p1"))
    reg = registry.transition("p1", ProviderState.CANDIDATE)
    assert reg.qualified_at is None
    registry.transition("p1", ProviderState.QUALIFIED)
    reg = registry.transition("p1", ProviderState.ACTIVE)
    assert reg.qualified_at is not None
    # candidate -> active is not a legal jump
    registry.register(_reg("p2"))
    with pytest.raises(ProviderError, match="illegal transition"):
        registry.transition("p2", ProviderState.ACTIVE)


def test_deterministic_selection_priority_then_id() -> None:
    registry = ProviderRegistry()
    for pid, prio in (("b_low", 1), ("a_high", 50), ("c_high_idtie", 50)):
        registry.register(_reg(pid, priority=prio))
        registry.transition(pid, ProviderState.CANDIDATE)
        registry.transition(pid, ProviderState.QUALIFIED)
        registry.transition(pid, ProviderState.ACTIVE)
    chosen = registry.select(ProviderCategory.AGENT_DISCOVERY)
    assert chosen.provider_id == "a_high"  # priority first, id tiebreak second


def test_invoke_success_tags_provider_and_audits() -> None:
    registry = ProviderRegistry()
    provider = OkProvider()
    registry.register(_reg("p_ok", handler=provider))
    registry.transition("p_ok", ProviderState.CANDIDATE)
    registry.transition("p_ok", ProviderState.QUALIFIED)
    registry.transition("p_ok", ProviderState.ACTIVE)
    result = registry.invoke(ProviderCategory.AGENT_DISCOVERY, "probe", {"x": 1})
    assert result["ok"] is True
    assert result["provider"] == "p_ok"
    assert provider.calls == 1
    assert registry.audit[-1]["outcome"] == "allow"


def test_permission_failure_never_falls_back() -> None:
    registry = ProviderRegistry()
    deny = _reg("a_deny", priority=100, handler=DenyProvider())
    fallback_ok = _reg("z_fallback", priority=10, handler=OkProvider())
    for reg in (deny, fallback_ok):
        registry.register(reg)
        registry.transition(reg.provider_id, ProviderState.CANDIDATE)
        registry.transition(reg.provider_id, ProviderState.QUALIFIED)
        registry.transition(reg.provider_id, ProviderState.ACTIVE)
    with pytest.raises(PermissionError):
        registry.invoke(ProviderCategory.AGENT_DISCOVERY, "probe")
    assert DenyProvider.calls == 1  # no retry
    ok = fallback_ok.handler
    assert isinstance(ok, OkProvider) and ok.calls == 0  # no fallback switch
    assert registry.audit[-1]["outcome"] == "deny"


def test_candidate_testable_independently() -> None:
    registry = ProviderRegistry()
    provider = OkProvider()
    registry.register(_reg("p_cand", handler=provider))  # stays registered/candidate
    result = registry.invoke_provider("p_cand", "probe")
    assert result["provider"] == "p_cand"
    registry.transition("p_cand", ProviderState.CANDIDATE)
    result2 = registry.invoke_provider("p_cand", "probe2")
    assert result2["ok"] is True


def test_error_audited_and_raised_without_retry() -> None:
    class Flaky:
        calls = 0

        def invoke(self, operation: str, payload: dict) -> dict:
            type(self).calls += 1
            raise RuntimeError("boom")

    registry = ProviderRegistry()
    flaky = _reg("p_flaky", handler=Flaky())
    registry.register(flaky)
    registry.transition("p_flaky", ProviderState.CANDIDATE)
    registry.transition("p_flaky", ProviderState.QUALIFIED)
    registry.transition("p_flaky", ProviderState.ACTIVE)
    with pytest.raises(RuntimeError):
        registry.invoke(ProviderCategory.AGENT_DISCOVERY, "probe")
    assert Flaky.calls == 1
    assert registry.audit[-1]["outcome"] == "error"


def test_external_provider_invoke_is_honest() -> None:
    registry = ProviderRegistry()
    registry.register(
        ProviderRegistration(
            provider_id="js_ext",
            category=ProviderCategory.OPERATIONAL_PERSISTENCE,
            implementation="javascript",
            endpoint="http://127.0.0.1:19000",
            capabilities=["agents.config.read"],
            priority=100,
        )
    )
    registry.transition("js_ext", ProviderState.CANDIDATE)
    registry.transition("js_ext", ProviderState.QUALIFIED)
    registry.transition("js_ext", ProviderState.ACTIVE)
    with pytest.raises(ProviderError, match="no in-process handler"):
        registry.invoke(ProviderCategory.OPERATIONAL_PERSISTENCE, "agents.config.read")
    assert registry.audit[-1]["outcome"] == "error"


def test_descriptor_matches_g3_contract() -> None:
    registry = ProviderRegistry()
    registry.register(_reg("p_desc", cat=ProviderCategory.TASK_EXECUTION, handler=OkProvider()))
    registry.transition("p_desc", ProviderState.CANDIDATE)
    registry.transition("p_desc", ProviderState.QUALIFIED)
    registry.transition("p_desc", ProviderState.ACTIVE)
    descriptor = registry.to_descriptor("p_desc")
    schema = json.loads(
        (ROOT / "contracts" / "schemas" / "ProviderDescriptor.schema.json").read_text()
    )
    errors: list[str] = []
    check = _load_subset_check()
    check(descriptor, schema, "$", errors)
    assert errors == []
    assert descriptor["provider_id"] == "p_desc"


def test_lifespan_registers_deployed_js_top_priority() -> None:
    async def drive() -> None:
        app = create_app(Settings())
        async with app.router.lifespan_context(app):
            registry = app.state.container.registry
            reg = registry.select(ProviderCategory.OPERATIONAL_PERSISTENCE)
            assert reg.provider_id == "pixel_office_js"
            assert reg.state is ProviderState.ACTIVE
            assert reg.priority == 100
            assert reg.qualified_at is not None
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                assert (await c.get("/healthz")).status_code == 200
        assert app.state.container.shutdowns == 1

    anyio.run(drive)
