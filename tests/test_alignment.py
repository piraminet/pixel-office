"""G9 employee/character alignment: lifecycle, impersonation guard, binding verify,
visual-sync non-destructiveness, decorative classification, restart survival."""

import json
import os

import anyio
import pytest

from pixel_startup.config import Settings
from pixel_startup.main import create_app
from pixel_startup.persistence.db import Database, StorageError
from pixel_startup.persistence.store import (
    EmployeeStore,
    align_employee_roster,
    migrate_office_json,
)

ROSTER = [
    {
        "id": 2,
        "name": "Charon",
        "role": "Concierge",
        "room": "Reception",
        "color": 2,
        "x": 320,
        "y": 236,
        "state": "idle",
        "active": True,
    },
    {
        "id": 6,
        "name": "Ghostface",
        "role": "Owner",
        "room": "Reception",
        "color": 6,
        "x": 420,
        "y": 180,
        "state": "idle",
        "active": False,
    },
]


def _db(tmp_path):
    db = Database(tmp_path / "ops.sqlite3")
    db.migrate()
    return db


def _roster(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text(json.dumps(ROSTER))
    return str(path)


def test_lifecycle_transitions_and_guards(tmp_path) -> None:
    db = _db(tmp_path)
    store = EmployeeStore(db)
    store.upsert(
        {
            "employee_id": "employee.charon",
            "display_name": "Charon",
            "sprite_id": "char_2",
            "harness": "none",
            "lifecycle": "registered",
        }
    )
    assert store.set_lifecycle("employee.charon", "available")["lifecycle"] == "available"
    assert store.set_lifecycle("employee.charon", "working")["lifecycle"] == "working"
    with pytest.raises(StorageError):
        store.set_lifecycle("employee.charon", "registered")  # working -> registered illegal
    with pytest.raises(StorageError):
        store.set_lifecycle("employee.ghost", "available")  # unknown employee
    # lifecycle is registry state, independent of session activity: employee may
    # be 'working' while no harness probe has ever run (no false availability)
    charon = store.get("employee.charon")
    assert charon is not None and charon["kind"] == "operational"  # migration 2 default
    db.close()


def test_bind_requires_proof_and_unique_index_refuses_impersonation(tmp_path) -> None:
    db = _db(tmp_path)
    store = EmployeeStore(db)
    for eid in ("employee.charon", "employee.wardog"):
        store.upsert(
            {
                "employee_id": eid,
                "display_name": eid,
                "sprite_id": "char_2",
                "harness": "none",
                "lifecycle": "registered",
            }
        )
    with pytest.raises(StorageError):
        store.bind("employee.charon", "openclaw", "", "gw-1")  # no native id
    with pytest.raises(StorageError):
        store.bind("employee.charon", "slack", "prof-9", "gw-1")  # unknown harness
    bound = store.bind(
        "employee.charon",
        "openclaw",
        "agent.charon.001",
        "gateway.instance-A",
        profile_label="default",
        provenance="G7 gateway discovery",
    )
    assert bound["binding_id"] == "binding.employee.charon.openclaw.agent.charon.001"
    after_bind = store.get("employee.charon")
    assert after_bind is not None and after_bind["verified_binding"] is None
    with pytest.raises(StorageError, match="impersonation"):
        store.bind("employee.wardog", "openclaw", "agent.charon.001", "gateway.instance-A")
    verified = store.verify_binding(
        "employee.charon", "binding.employee.charon.openclaw.agent.charon.001"
    )
    assert verified["verified_binding"] == {
        "binding_id": "binding.employee.charon.openclaw.agent.charon.001",
        "verified": True,
    }
    with pytest.raises(StorageError):
        store.verify_binding(
            "employee.wardog",  # foreign binding refused
            "binding.employee.charon.openclaw.agent.charon.001",
        )
    rows = db.conn.execute("SELECT COUNT(*) AS n FROM runtime_bindings").fetchone()
    assert rows["n"] == 1  # rejected bind left no row
    db.close()


def test_visual_sync_never_clobbers_bindings(tmp_path) -> None:
    path = tmp_path / "agents.json"
    path.write_text(json.dumps(ROSTER))
    db = _db(tmp_path)
    store = EmployeeStore(db)
    migrate_office_json(db, str(path))
    store.bind("employee.charon", "openclaw", "agent.charon.001", "gw-i")
    migrate_office_json(db, str(path))  # re-run (e.g. boot of restarted office)
    row = store.get("employee.charon")
    assert row is not None
    assert row["harness"] == "openclaw"  # binding survived the visual sync
    assert row["verified_binding"] is None or row["native_harness_id"] == "agent.charon.001"
    db.close()


def test_align_classification_intents_and_observed_passthrough(tmp_path) -> None:
    db = _db(tmp_path)
    path = _roster(tmp_path)
    report = align_employee_roster(
        db,
        path,
        kind_map={"employee.ghostface": "decorative"},
        harness_intents={"employee.charon": "openclaw"},
        observed={"openclaw": {"online": False}, "hermes": {"online": True}},
    )
    by_id = {e["employee_id"]: e for e in report["employees"]}
    assert by_id["employee.ghostface"]["kind"] == "decorative"  # distinguishable
    assert by_id["employee.charon"]["harness"] == "openclaw"
    assert by_id["employee.charon"]["native_agent_id"] is None  # intent, not a binding
    assert report["pending_bindings"] == [
        {
            "employee_id": "employee.charon",
            "harness": "openclaw",
            "reason": "awaiting native agent id + instance proof",
        }
    ]
    # observed probes pass through verbatim; Charon lifecycle NOT derived from them
    assert report["observed_runtime"]["openclaw"] == {"online": False}
    assert by_id["employee.charon"]["lifecycle"] == "registered"
    again = align_employee_roster(
        db,
        path,
        kind_map={"employee.ghostface": "decorative"},
        harness_intents={"employee.charon": "openclaw"},
    )
    assert again["employees_upserted"] == report["employees_upserted"]  # idempotent
    db.close()


def test_boot_alignment_survives_restart_and_audits(tmp_path) -> None:
    async def drive() -> None:
        data = tmp_path / "data"
        data.mkdir()
        (data / "agents.json").write_text(json.dumps(ROSTER))
        for _ in range(2):  # two boots (restart)
            app = create_app(
                Settings(pixel_data_dir=str(data), hermes_home=str(tmp_path / "no-hermes"))
            )
            async with app.router.lifespan_context(app):
                store = app.state.container.providers["employees"]
                assert store.count() == 2
                charon = store.get("employee.charon")
                assert charon["harness"] == "openclaw"  # intent recorded at each boot
                assert charon["native_harness_id"] == ""  # but never auto-bound
        final = Database(str(data / "pixel_startup.sqlite3"))
        audits = final.conn.execute(
            "SELECT event_id FROM audit_events WHERE action = 'office.roster.align'"
        ).fetchall()
        assert len(audits) == 1  # idempotent by source sha: one alignment event
        final.close()
        assert os.path.isfile(str(data / "agents.json"))  # visual source intact

    anyio.run(drive)
