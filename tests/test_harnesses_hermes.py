"""G8 Hermes adapter: live-filesystem probe with a synthetic $HERMES_HOME fixture."""

import json
import os

import anyio
import pytest

from pixel_startup.config import Settings
from pixel_startup.harnesses.hermes import HermesHomeAdapter, _pid_alive
from pixel_startup.main import create_app
from pixel_startup.providers.registry import ProviderState


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    (home / "runtime").mkdir(parents=True)
    (home / "profiles" / "side").mkdir(parents=True)
    (home / "gateway_state.json").write_text(
        json.dumps(
            {
                "pid": os.getpid(),  # provably alive
                "gateway_state": "running",
                "active_agents": 2,
                "platforms": {"mattermost": {"state": "connected"}},
            }
        )
    )
    (home / "runtime" / "active_sessions.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"session_id": "s_live", "surface": "cli", "pid": os.getpid(), "started_at": 1},
                    {"session_id": "s_dead", "surface": "cli", "pid": 99999999, "started_at": 2},
                ]
            }
        )
    )
    return home


def _adapter(home, liveness_fn=None) -> HermesHomeAdapter:
    return HermesHomeAdapter(hermes_home=str(home), liveness_fn=liveness_fn)


def test_gateway_health_live_gateway_and_session_filtering(hermes_home) -> None:
    result = _adapter(hermes_home).invoke("gateway.health")
    probe = result["result"]
    assert probe["online"] is True
    assert probe["gateway"]["state"] == "running"
    assert probe["platforms"] == ["mattermost"]
    assert [s["session_id"] for s in probe["sessions"]] == ["s_live"]  # dead lease filtered
    assert "default" in probe["profiles"] and "side" in probe["profiles"]


def test_offline_home_is_honest(hermes_home) -> None:
    empty = hermes_home / "empty"
    empty.mkdir()
    probe = _adapter(empty).invoke("gateway.health")["result"]
    assert probe["online"] is False
    assert probe["gateway"]["state"] == "offline"
    assert probe["sessions"] == []


def test_profile_discovery_and_liveness_helper(hermes_home) -> None:
    discovery = _adapter(hermes_home).invoke("profile.discovery")["result"]
    assert "default" in discovery["profiles"]
    assert discovery["live_sessions"][0]["session_id"] == "s_live"
    assert "G9" in discovery["bindings"]
    assert _pid_alive("not-a-pid") is False


def test_unsupported_task_operations_explicit(hermes_home) -> None:
    adapter = _adapter(hermes_home)
    for op in ("task.submit", "task.result", "task.cancel", "activity.observe"):
        result = adapter.invoke(op)
        assert result["supported"] is False and result["operation"] == op
    assert adapter.invoke("nope")["reason"] == "unknown operation"


def test_evidence_gated_promotion(hermes_home, tmp_path) -> None:
    async def drive() -> None:
        # live hermes home ->QUALIFIED (honest promotion)
        app = create_app(
            Settings(pixel_data_dir=str(tmp_path / "d1"), hermes_home=str(hermes_home))
        )
        async with app.router.lifespan_context(app):
            reg = app.state.container.registry.get("hermes_home")
            assert reg.state is ProviderState.QUALIFIED
        # empty hermes home -> stays CANDIDATE, startup still fine
        empty = hermes_home / "empty2"
        empty.mkdir()
        app2 = create_app(Settings(pixel_data_dir=str(tmp_path / "d2"), hermes_home=str(empty)))
        async with app2.router.lifespan_context(app2):
            reg2 = app2.state.container.registry.get("hermes_home")
            assert reg2.state is ProviderState.CANDIDATE

    anyio.run(drive)
