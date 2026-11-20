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

from pixel_startup.persistence.db import TASK_TRANSITIONS, Database, StorageError, _now

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
        return dict(found) if found else None


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
    stable employee_id — visual characters land unbound (harness='none');
    runtime binding is G7/G8 territory. Source file is read-only.
    """
    raw = open(agents_json_path, "rb").read()
    source_sha256 = hashlib.sha256(raw).hexdigest()
    roster = json.loads(raw)
    store = EmployeeStore(db)
    upserted = 0
    for agent in roster:
        name = str(agent.get("name", f"agent_{agent.get('id')}"))
        employee = {
            "employee_id": f"employee.{name.lower()}",
            "display_name": name,
            "sprite_id": f"char_{agent.get('id')}",
            "harness": "none",  # visual character until a harness binding is proven
            "native_harness_id": "",
            "harness_instance_id": "",
            "session_id": "",
            "current_task_id": "",
            "operational_scope": "shared",
            "authorization_context": [],
            "lifecycle": "registered" if agent.get("active", True) else "offline",
            "asserted_id": f"employee.{name.lower()}",
            "verified_binding": None,
        }
        store.upsert(employee)
        upserted += 1
    return {"employees_upserted": upserted, "source_sha256": source_sha256}
