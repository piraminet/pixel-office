"""Operational stores over the versioned schema: employees, tasks, approvals, audit.

Every write is an atomic single-transaction upsert/update; task transitions are
CAS-guarded (UPDATE ... WHERE status = expected) so interrupted writes cannot
half-apply. JSON migration utilities are repeatable and non-destructive: the
source files are read-only inputs and upserts key on stable identifiers, so
re-running never duplicates rows.
"""

import hashlib
import json
import sqlite3

from pixel_startup.persistence.db import (
    EMPLOYEE_LIFECYCLE_TRANSITIONS,
    TASK_TRANSITIONS,
    Database,
    StorageError,
    _now,
)

EMPLOYEE_COLUMNS = (
    "employee_id",
    "display_name",
    "sprite_id",
    "harness",
    "native_harness_id",
    "harness_instance_id",
    "session_id",
    "current_task_id",
    "operational_scope",
    "authorization_context",
    "lifecycle",
    "asserted_id",
    "verified_binding",
    "kind",
    "updated_at",
)


class EmployeeStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, employee: dict, when: str | None = None) -> None:
        row = {c: employee.get(c) for c in EMPLOYEE_COLUMNS if c != "updated_at"}
        row["authorization_context"] = json.dumps(row.get("authorization_context") or [])
        row["updated_at"] = when or _now()
        self.db.conn.execute("BEGIN IMMEDIATE")
        try:
            self.db.conn.execute(
                f"INSERT OR REPLACE INTO employees ({', '.join(EMPLOYEE_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in EMPLOYEE_COLUMNS)})",
                [row[c] for c in EMPLOYEE_COLUMNS],
            )
            self.db.conn.execute("COMMIT")
        except Exception:
            self.db.conn.execute("ROLLBACK")
            raise

    def count(self) -> int:
        row = self.db.conn.execute("SELECT COUNT(*) AS n FROM employees").fetchone()
        return int(row["n"])

    def get(self, employee_id: str) -> dict | None:
        cur = self.db.conn.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
        found = cur.fetchone()
        if not found:
            return None
        row = dict(found)
        row["authorization_context"] = json.loads(row.get("authorization_context") or "[]")
        row["verified_binding"] = (
            json.loads(row["verified_binding"]) if row.get("verified_binding") else None
        )
        return row

    def all(self) -> list[dict]:
        cur = self.db.conn.execute("SELECT * FROM employees ORDER BY employee_id")
        out = []
        for found in cur.fetchall():
            row = dict(found)
            row["authorization_context"] = json.loads(row.get("authorization_context") or "[]")
            row["verified_binding"] = (
                json.loads(row["verified_binding"]) if row.get("verified_binding") else None
            )
            out.append(row)
        return out

    def _write(self, employee_id: str, assignments: dict, expected_lifecycle: str) -> dict:
        """CAS update: assignments applied only while the expected lifecycle holds."""
        sets = ", ".join(f"{c} = ?" for c in assignments)
        values = list(assignments.values()) + [_now(), employee_id, expected_lifecycle]
        cur = self.db.conn.execute(
            f"UPDATE employees SET {sets}, updated_at = ? WHERE employee_id = ? AND lifecycle = ?",
            values,
        )
        if cur.rowcount != 1:
            row = self.get(employee_id)
            current = row["lifecycle"] if row else None
            if current is None:
                raise StorageError(f"unknown employee: {employee_id}")
            raise StorageError(
                f"stale or illegal update for {employee_id} (lifecycle now {current})"
            )
        return self.get(employee_id) or {}

    def set_lifecycle(self, employee_id: str, new_status: str) -> dict:
        current = self.get(employee_id)
        if current is None:
            raise StorageError(f"unknown employee: {employee_id}")
        if new_status not in EMPLOYEE_LIFECYCLE_TRANSITIONS.get(current["lifecycle"], set()):
            raise StorageError(f"illegal lifecycle {current['lifecycle']} -> {new_status}")
        return self._write(employee_id, {"lifecycle": new_status}, current["lifecycle"])

    def bind(
        self,
        employee_id: str,
        harness: str,
        native_agent_id: str,
        harness_instance_id: str,
        profile_label: str = "",
        provenance: str = "",
    ) -> dict:
        """Bind a native harness identity (mandate: instance + native id mandatory).

        Uniqueness is enforced by the partial unique index (migration 2): a
        native identity may belong to exactly one employee — the impersonation
        guard. verified_binding is NOT granted here; only verify() grants it."""
        if harness not in ("openclaw", "hermes"):
            raise StorageError(f"unsupported harness: {harness}")
        if not native_agent_id or not harness_instance_id:
            raise StorageError("native_agent_id and harness_instance_id are required")
        binding_id = f"binding.{employee_id}.{harness}.{native_agent_id}"
        self.db.conn.execute("BEGIN IMMEDIATE")
        try:
            self.db.conn.execute(
                "INSERT OR REPLACE INTO runtime_bindings (binding_id, employee_id, harness,"
                " harness_instance_id, native_agent_id, profile_label, bound_at, active,"
                " provenance) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    binding_id,
                    employee_id,
                    harness,
                    harness_instance_id,
                    native_agent_id,
                    profile_label,
                    _now(),
                    provenance,
                ),
            )
            self.db.conn.execute(
                "UPDATE employees SET harness = ?, native_harness_id = ?,"
                " harness_instance_id = ?, updated_at = ? WHERE employee_id = ?",
                (harness, native_agent_id, harness_instance_id, _now(), employee_id),
            )
            self.db.conn.execute("COMMIT")
        except sqlite3.IntegrityError:
            self.db.conn.execute("ROLLBACK")
            raise StorageError(
                f"impersonation refusal: {harness}:{native_agent_id} is already bound"
            ) from None
        except Exception:
            self.db.conn.execute("ROLLBACK")
            raise
        return {"binding_id": binding_id, **(self.get(employee_id) or {})}

    def verify_binding(self, employee_id: str, binding_id: str) -> dict:
        """Grant verified_binding only for an existing, active binding row."""
        row = self.db.conn.execute(
            "SELECT active FROM runtime_bindings WHERE binding_id = ?", (binding_id,)
        ).fetchone()
        if row is None or not row["active"]:
            raise StorageError(f"unknown or inactive binding: {binding_id}")
        claimed = self.get(employee_id)
        if claimed is None:
            raise StorageError(f"unknown employee: {employee_id}")
        expected = f"binding.{employee_id}.{claimed['harness']}.{claimed['native_harness_id']}"
        if binding_id != expected:
            raise StorageError("binding does not belong to this employee")
        result = self._write(
            employee_id,
            {"verified_binding": json.dumps({"binding_id": binding_id, "verified": True})},
            claimed["lifecycle"],
        )
        return result


class TaskStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, task: dict) -> dict:
        """Idempotent create: same task_id returns the existing row untouched."""
        existing = self.get(task["task_id"])
        if existing is not None:
            return existing
        ts = _now()
        self.db.conn.execute("BEGIN IMMEDIATE")
        try:
            self.db.conn.execute(
                "INSERT INTO tasks (task_id, kind, objective, operational_scope, requested_by,"
                " assigned_employee_id, status, correlation_id, created_at, payload, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task["task_id"],
                    task["kind"],
                    task["objective"],
                    task.get("operational_scope", "shared"),
                    task.get("requested_by", "owner"),
                    task.get("assigned_employee_id"),
                    task.get("status", "created"),
                    task.get("correlation_id", task["task_id"]),
                    ts,
                    json.dumps(task["payload"]) if task.get("payload") is not None else None,
                    ts,
                ),
            )
            self.db.conn.execute("COMMIT")
        except sqlite3.IntegrityError:
            self.db.conn.execute("ROLLBACK")
            existing = self.get(task["task_id"])
            if existing is None:
                raise
            return existing
        except Exception:
            self.db.conn.execute("ROLLBACK")
            raise
        return self.get(task["task_id"]) or {}

    def get(self, task_id: str) -> dict | None:
        cur = self.db.conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        found = cur.fetchone()
        return dict(found) if found else None

    def transition(self, task_id: str, new_status: str) -> dict:
        """Atomic CAS transition; raises StorageError on unknown task or illegal move."""
        task = self.get(task_id)
        if task is None:
            raise StorageError(f"unknown task: {task_id}")
        current = task["status"]
        if new_status not in TASK_TRANSITIONS.get(current, set()):
            raise StorageError(f"illegal transition {current} -> {new_status}")
        cur = self.db.conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ? AND status = ?",
            (new_status, _now(), task_id, current),
        )
        if cur.rowcount != 1:
            raise StorageError(f"stale transition raced for {task_id}")
        return self.get(task_id) or {}


class ApprovalStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, request: dict) -> dict:
        self.db.conn.execute("BEGIN IMMEDIATE")
        try:
            self.db.conn.execute(
                "INSERT INTO approvals (request_id, task_id, requested_by, reason,"
                " operational_scope, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                (
                    request["request_id"],
                    request["task_id"],
                    request["requested_by"],
                    request["reason"],
                    request.get("operational_scope", "shared"),
                    _now(),
                ),
            )
            self.db.conn.execute("COMMIT")
        except Exception:
            self.db.conn.execute("ROLLBACK")
            raise
        return self.get(request["request_id"]) or {}

    def decide(self, request_id: str, decision: str, decided_by: str) -> dict:
        if decision not in ("approved", "denied"):
            raise StorageError(f"invalid decision: {decision}")
        cur = self.db.conn.execute(
            "UPDATE approvals SET status = ?, decided_by = ?, decided_at = ?"
            " WHERE request_id = ? AND status = 'pending'",
            (decision, decided_by, _now(), request_id),
        )
        if cur.rowcount != 1:
            raise StorageError(f"approval {request_id} not pending")
        return self.get(request_id) or {}

    def get(self, request_id: str) -> dict | None:
        cur = self.db.conn.execute("SELECT * FROM approvals WHERE request_id = ?", (request_id,))
        found = cur.fetchone()
        return dict(found) if found else None


class AuditStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, event: dict) -> None:
        self.db.conn.execute("BEGIN IMMEDIATE")
        try:
            self.db.conn.execute(
                "INSERT OR REPLACE INTO audit_events (event_id, occurred_at, actor,"
                " action, outcome, detail) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event["event_id"],
                    event.get("occurred_at", _now()),
                    event.get("actor", "system"),
                    event.get("action", "event"),
                    event.get("outcome", "allow"),
                    json.dumps(event.get("detail", {})),
                ),
            )
            self.db.conn.execute("COMMIT")
        except Exception:
            self.db.conn.execute("ROLLBACK")
            raise

    def count(self) -> int:
        row = self.db.conn.execute("SELECT COUNT(*) AS n FROM audit_events").fetchone()
        return int(row["n"])


class OfficePersistenceProvider:
    """G5 provider handler for the Python operational store (read-only ops for now)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def invoke(self, operation: str, payload: dict) -> dict:
        if operation == "health.counts":
            counts = {}
            for table in ("employees", "runtime_bindings", "tasks", "approvals", "audit_events"):
                row = self.db.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
                counts[table] = int(row["n"])
            return {"counts": counts}
        raise StorageError(f"unsupported operation: {operation}")


def migrate_office_json(db: Database, agents_json_path: str) -> dict:
    """Repeatable, non-destructive migration of the JS office roster.

    Reads data/agents.json (visual roster) and upserts employees keyed by
    stable employee_id. Visual sync touches ONLY visual identity fields
    (display_name, sprite_id) — harness bindings, lifecycle and verified
    bindings are never clobbered on re-run. Source file is read-only.
    """
    raw = open(agents_json_path, "rb").read()
    source_sha256 = hashlib.sha256(raw).hexdigest()
    roster = json.loads(raw)
    upserted = 0
    for agent in roster:
        name = str(agent.get("name", f"agent_{agent.get('id')}"))
        employee_id = f"employee.{name.lower()}"
        db.conn.execute("BEGIN IMMEDIATE")
        try:
            db.conn.execute(
                "INSERT INTO employees (employee_id, display_name, sprite_id, harness,"
                " native_harness_id, harness_instance_id, session_id, current_task_id,"
                " operational_scope, authorization_context, lifecycle, asserted_id,"
                " verified_binding, kind, updated_at)"
                " VALUES (?, ?, ?, 'none', '', '', '', '', 'shared', '[]', ?, ?, NULL,"
                " 'operational', ?)"
                " ON CONFLICT(employee_id) DO UPDATE SET"
                " display_name = excluded.display_name, sprite_id = excluded.sprite_id,"
                " updated_at = excluded.updated_at",
                (
                    employee_id,
                    name,
                    f"char_{agent.get('id')}",
                    "registered" if agent.get("active", True) else "offline",
                    employee_id,
                    _now(),
                ),
            )
            db.conn.execute("COMMIT")
        except Exception:
            db.conn.execute("ROLLBACK")
            raise
        upserted += 1
    return {"employees_upserted": upserted, "source_sha256": source_sha256}


def align_employee_roster(
    db: Database,
    agents_json_path: str,
    kind_map: dict[str, str] | None = None,
    harness_intents: dict[str, str] | None = None,
    observed: dict | None = None,
) -> dict:
    """G9 employee/character alignment.

    Visual characters stay the visual layer's data; the registry records
    classification (kind), harness INTENT (never auto-bound — a native id plus
    harness-instance proof is required before verified_binding), and passes
    observed runtime probe results through verbatim WITHOUT deriving employee
    lifecycle from them (no false 'available' from probe output).
    """
    migrated = migrate_office_json(db, agents_json_path)
    kind_map = kind_map or {}
    for employee_id, kind in kind_map.items():
        if kind not in ("operational", "decorative"):
            raise StorageError(f"invalid kind: {kind}")
        db.conn.execute("UPDATE employees SET kind = ? WHERE employee_id = ?", (kind, employee_id))
    harness_intents = harness_intents or {}
    pending_bindings = []
    for employee_id, harness in harness_intents.items():
        # intent never overwrites an existing proof-backed binding
        db.conn.execute(
            "UPDATE employees SET harness = ?, updated_at = ?"
            " WHERE employee_id = ? AND native_harness_id = ''",
            (harness, _now(), employee_id),
        )
        row = db.conn.execute(
            "SELECT native_harness_id FROM employees WHERE employee_id = ?",
            (employee_id,),
        ).fetchone()
        if row is None or not row["native_harness_id"]:
            pending_bindings.append(
                {
                    "employee_id": employee_id,
                    "harness": harness,
                    "reason": "awaiting native agent id + instance proof",
                }
            )
    store = EmployeeStore(db)
    employees = [
        {
            "employee_id": e["employee_id"],
            "display_name": e["display_name"],
            "sprite_id": e["sprite_id"],
            "kind": e["kind"],
            "lifecycle": e["lifecycle"],
            "harness": e["harness"],
            "native_agent_id": e["native_harness_id"] or None,
            "verified_binding": e["verified_binding"],
        }
        for e in store.all()
    ]
    return {
        **migrated,
        "employees": employees,
        "pending_bindings": pending_bindings,
        "observed_runtime": observed or {},
    }
