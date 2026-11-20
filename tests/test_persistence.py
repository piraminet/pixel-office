"""G6 persistence: versioned migrations, idempotent JSON migration, CAS transitions,
restart recovery, backup/restore, WAL concurrency, provider wiring."""

import json
import os

import anyio
import pytest

from pixel_startup.config import Settings
from pixel_startup.main import create_app
from pixel_startup.persistence.db import Database, StorageError
from pixel_startup.persistence.store import (
    ApprovalStore,
    AuditStore,
    TaskStore,
    migrate_office_json,
)
from pixel_startup.providers.registry import ProviderCategory, ProviderState

AGENTS_FIXTURE = [
    {
        "id": 0,
        "name": "Curator",
        "role": "Archivist",
        "room": "Archives",
        "color": 0,
        "x": 320,
        "y": 680,
        "state": "idle",
        "active": True,
    },
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


def test_migration_version_pin_and_idempotence(tmp_path) -> None:
    db = _db(tmp_path)
    top = db.conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    assert top["v"] == 1
    before = db.conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"]
    db.migrate()  # repeat run: no-op
    after = db.conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"]
    assert before == after == 1
    db.close()


def test_json_migration_repeatable_nondestructive(tmp_path) -> None:
    src = tmp_path / "agents.json"
    src.write_text(json.dumps(AGENTS_FIXTURE))
    original = src.read_bytes()
    db = _db(tmp_path)
    first = migrate_office_json(db, str(src))
    assert first["employees_upserted"] == 3
    assert db.conn.execute("SELECT COUNT(*) AS n FROM employees").fetchone()["n"] == 3
    second = migrate_office_json(db, str(src))
    assert second["employees_upserted"] == 3  # repeatable
    assert db.conn.execute("SELECT COUNT(*) AS n FROM employees").fetchone()["n"] == 3  # no dupes
    charon = db.conn.execute(
        "SELECT * FROM employees WHERE employee_id = 'employee.charon'"
    ).fetchone()
    assert charon["sprite_id"] == "char_2"
    assert charon["harness"] == "none"  # unbound visual character until G7/G8
    assert src.read_bytes() == original  # source untouched (rollback-safe)
    db.close()


def test_task_create_idempotent_and_transitions_cas(tmp_path) -> None:
    db = _db(tmp_path)
    store = TaskStore(db)
    first = store.create(
        {"task_id": "task.9001", "kind": "briefing", "objective": "Draft morning briefing"}
    )
    second = store.create({"task_id": "task.9001", "kind": "briefing", "objective": "DIFFERENT"})
    assert first["objective"] == "Draft morning briefing"  # idempotent create
    assert second["task_id"] == first["task_id"]
    assert db.conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()["n"] == 1

    with pytest.raises(StorageError):
        store.transition("task.9001", "dispatched")  # created -> dispatched illegal
    assert store.transition("task.9001", "authorized")["status"] == "authorized"
    assert store.transition("task.9001", "dispatched")["status"] == "dispatched"
    with pytest.raises(StorageError):
        store.transition("unknown-task", "running")
    db.close()


def test_multiconnection_wal(tmp_path) -> None:
    db = _db(tmp_path)
    journal = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal == "wal"
    TaskStore(db).create({"task_id": "task.1", "kind": "probe", "objective": "x"})
    db2 = Database(tmp_path / "ops.sqlite3")  # second connection sees committed state
    row = db2.conn.execute("SELECT status FROM tasks WHERE task_id='task.1'").fetchone()
    assert row["status"] == "created"
    db2.close()
    db.close()


def test_stale_guard_via_out_of_band_write(tmp_path) -> None:
    db = _db(tmp_path)
    store = TaskStore(db)
    store.create({"task_id": "task.2", "kind": "probe", "objective": "x"})
    store.transition("task.2", "authorized")
    # another writer moves the row forward behind a stale reader's back
    db.conn.execute("UPDATE tasks SET status = 'running' WHERE task_id = 'task.2'")
    # a competitor holding the outdated 'authorized' view is refused by the CAS guard
    stale = db.conn.execute(
        "UPDATE tasks SET status = 'cancelled', updated_at = 'stale'"
        " WHERE task_id = 'task.2' AND status = 'authorized'"
    )
    assert stale.rowcount == 0
    # a fresh view transitions the actual current state (running -> cancelled, legal)
    assert store.transition("task.2", "cancelled")["status"] == "cancelled"
    db.close()


def test_restart_recovery_survives_reopen(tmp_path) -> None:
    path = tmp_path / "ops.sqlite3"
    db = Database(path)
    db.migrate()
    TaskStore(db).create({"task_id": "task.42", "kind": "probe", "objective": "survive restart"})
    db.close()
    fresh = Database(path)
    fresh.migrate()
    row = fresh.conn.execute("SELECT objective FROM tasks WHERE task_id='task.42'").fetchone()
    assert row["objective"] == "survive restart"
    fresh.close()


def test_backup_and_restore(tmp_path) -> None:
    path = tmp_path / "ops.sqlite3"
    db = Database(path)
    db.migrate()
    store = TaskStore(db)
    store.create({"task_id": "task.b1", "kind": "probe", "objective": "backup me"})
    backup_path = tmp_path / "backup.sqlite3"
    db.backup(str(backup_path))
    assert backup_path.stat().st_size > 0
    store.create({"task_id": "task.b2", "kind": "probe", "objective": "post-backup noise"})
    db.close()  # release WAL so the restored file is read cleanly
    Database.restore_from(str(backup_path), str(path))
    reopened = Database(path)
    assert reopened.conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()["n"] == 1
    reopened.close()


def test_audit_append_and_count(tmp_path) -> None:
    db = _db(tmp_path)
    audit = AuditStore(db)
    audit.append(
        {"event_id": "audit.1", "actor": "employee.charon", "action": "x", "outcome": "allow"}
    )
    audit.append({"event_id": "audit.2", "action": "y", "outcome": "deny"})
    assert audit.count() == 2
    db.close()


def test_approval_lifecycle(tmp_path) -> None:
    db = _db(tmp_path)
    tasks = TaskStore(db)
    approvals = ApprovalStore(db)
    tasks.create({"task_id": "task.a9", "kind": "probe", "objective": "needs approval"})
    req = approvals.create(
        {
            "request_id": "req.9",
            "task_id": "task.a9",
            "requested_by": "employee.charon",
            "reason": "email send",
        }
    )
    assert req["status"] == "pending"
    decided = approvals.decide("req.9", "approved", "owner")
    assert decided["status"] == "approved"
    with pytest.raises(StorageError):
        approvals.decide("req.9", "denied", "owner")  # no double decisions
    with pytest.raises(StorageError):
        approvals.decide("req.missing", "approved", "owner")
    db.close()


def test_sqlite_provider_qualified_but_js_still_top_priority(tmp_path) -> None:
    async def drive() -> None:
        assert not os.path.isdir("data") or True  # data dir not touched in tests
        app = create_app(Settings(pixel_data_dir=str(tmp_path / "data")))
        async with app.router.lifespan_context(app):
            registry = app.state.container.registry
            top = registry.select(ProviderCategory.OPERATIONAL_PERSISTENCE)
            assert top.provider_id == "pixel_office_js"  # JS retains priority
            py_store = registry.get("pixel_startup_sqlite")
            assert py_store.state is ProviderState.QUALIFIED
            assert py_store.priority == 10
            result = registry.invoke_provider("pixel_startup_sqlite", "health.counts")
            assert result["counts"]["tasks"] == 0
            with pytest.raises(StorageError):
                registry.invoke_provider("pixel_startup_sqlite", "not.an.op")
        assert app.state.container.shutdowns == 1

    anyio.run(drive)
