"""Provider and component architecture (G5).

Categories and states are exactly the mandate set. Rules enforced here:

- Explicit promotion only: `register()` never lands in `active`; transitions are
  validated against a legal-transition table.
- Deterministic selection: highest priority wins, ties broken by provider_id.
- No fallback, ever, and no silent switching after a permission failure:
  `invoke()` audits and re-raises. There is no retry (side-effecting operations
  have no established idempotency guarantee yet).
- Usage is auditable: every invoke appends a sanitized audit record.
"""

import time
from dataclasses import dataclass, field
from enum import Enum

from pixel_startup.log import logger  # noqa: F401  (kept for future provider events)

CATEGORY_VALUES = (
    "agent_harness",
    "agent_discovery",
    "task_execution",
    "memory_retrieval",
    "object_storage",
    "comms_internal",
    "comms_external",
    "credential_execution",
    "monitoring",
    "automation",
    "activity_reporting",
    "operational_persistence",
)
STATE_VALUES = (
    "discovered",
    "registered",
    "candidate",
    "qualified",
    "active",
    "deprecated",
    "disabled",
)


class ProviderCategory(str, Enum):
    AGENT_HARNESS = "agent_harness"
    AGENT_DISCOVERY = "agent_discovery"
    TASK_EXECUTION = "task_execution"
    MEMORY_RETRIEVAL = "memory_retrieval"
    OBJECT_STORAGE = "object_storage"
    COMMS_INTERNAL = "comms_internal"
    COMMS_EXTERNAL = "comms_external"
    CREDENTIAL_EXECUTION = "credential_execution"
    MONITORING = "monitoring"
    AUTOMATION = "automation"
    ACTIVITY_REPORTING = "activity_reporting"
    OPERATIONAL_PERSISTENCE = "operational_persistence"


class ProviderState(str, Enum):
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    CANDIDATE = "candidate"
    QUALIFIED = "qualified"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class ProviderError(Exception):
    """Registry misuse or unavailable provider (not an authorization failure)."""


LEGAL_TRANSITIONS: dict[ProviderState, frozenset[ProviderState]] = {
    ProviderState.DISCOVERED: frozenset({ProviderState.REGISTERED, ProviderState.DISABLED}),
    ProviderState.REGISTERED: frozenset({ProviderState.CANDIDATE, ProviderState.DISABLED}),
    ProviderState.CANDIDATE: frozenset(
        {ProviderState.QUALIFIED, ProviderState.REGISTERED, ProviderState.DISABLED}
    ),
    ProviderState.QUALIFIED: frozenset(
        {ProviderState.ACTIVE, ProviderState.CANDIDATE, ProviderState.DISABLED}
    ),
    ProviderState.ACTIVE: frozenset({ProviderState.DEPRECATED, ProviderState.DISABLED}),
    ProviderState.DEPRECATED: frozenset({ProviderState.DISABLED}),
    ProviderState.DISABLED: frozenset(),
}


@dataclass
class ProviderRegistration:
    provider_id: str
    category: ProviderCategory
    implementation: str  # python | javascript | external
    state: ProviderState = ProviderState.REGISTERED
    endpoint: str | None = None
    capabilities: list[str] = field(default_factory=list)
    priority: int = 0
    qualified_at: str | None = None
    # In-process provider interface (optional). Contract: invoke(operation, payload) -> dict
    handler: object | None = None
    detail: str | None = None


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderRegistration] = {}
        self.audit: list[dict[str, object]] = []

    # -- registration -------------------------------------------------------
    def register(self, reg: ProviderRegistration) -> ProviderRegistration:
        if reg.provider_id in self._providers:
            raise ProviderError(f"provider already registered: {reg.provider_id}")
        if reg.state not in (
            ProviderState.DISCOVERED,
            ProviderState.REGISTERED,
            ProviderState.CANDIDATE,
        ):
            raise ProviderError(
                f"register() cannot promote: {reg.provider_id} state={reg.state.value}"
            )
        self._providers[reg.provider_id] = reg
        return reg

    def get(self, provider_id: str) -> ProviderRegistration:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ProviderError(f"unknown provider: {provider_id}") from exc

    def all(self) -> list[ProviderRegistration]:
        return sorted(self._providers.values(), key=lambda p: p.provider_id)

    # -- explicit lifecycle -------------------------------------------------
    def transition(self, provider_id: str, new_state: ProviderState) -> ProviderRegistration:
        reg = self.get(provider_id)
        if new_state not in LEGAL_TRANSITIONS[reg.state]:
            raise ProviderError(
                f"illegal transition {reg.state.value} -> {new_state.value} for {provider_id}"
            )
        reg.state = new_state
        if new_state is ProviderState.QUALIFIED and reg.qualified_at is None:
            reg.qualified_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.audit.append(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "provider_id": provider_id,
                "action": "transition",
                "outcome": "allow",
                "detail": new_state.value,
            }
        )
        logger.info(
            "provider transition",
            extra={
                "event": "provider.transition",
                "component": provider_id,
                "detail": new_state.value,
            },
        )  # noqa: E501
        return reg

    # -- selection ----------------------------------------------------------
    def select(self, category: ProviderCategory) -> ProviderRegistration:
        actives = [
            p
            for p in self._providers.values()
            if p.category is category and p.state is ProviderState.ACTIVE
        ]
        if not actives:
            raise ProviderError(f"no active provider for category {category.value}")
        return sorted(actives, key=lambda p: (-p.priority, p.provider_id))[0]

    # -- invocation (no fallback / no retry) ---------------------------------
    def invoke(
        self, category: ProviderCategory, operation: str, payload: dict | None = None
    ) -> dict:
        reg = self.select(category)
        return self.invoke_provider(reg.provider_id, operation, payload)

    def invoke_provider(
        self, provider_id: str, operation: str, payload: dict | None = None
    ) -> dict:
        reg = self.get(provider_id)
        record: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "provider_id": provider_id,
            "category": reg.category.value,
            "operation": operation,
            "outcome": "allow",
            "detail": None,
        }
        if reg.handler is None:
            record["outcome"] = "error"
            record["detail"] = (
                f"external provider {reg.implementation}: in-process invoke unavailable"
            )
            self.audit.append(record)
            raise ProviderError(f"provider {provider_id} has no in-process handler")
        try:
            result = reg.handler.invoke(operation, payload or {})  # type: ignore[attr-defined]
        except PermissionError:
            record["outcome"] = "deny"
            record["detail"] = "authorization failure"
            self.audit.append(record)
            raise  # mandate: never switch providers after a permission failure
        except Exception as exc:  # noqa: BLE001 - audited re-raise, no silent fallback
            record["outcome"] = "error"
            record["detail"] = type(exc).__name__
            self.audit.append(record)
            raise
        result = dict(result or {})
        result["provider"] = provider_id
        self.audit.append(record)
        return result

    # -- descriptor contract (G3 ProviderDescriptor) -------------------------
    def to_descriptor(self, provider_id: str) -> dict[str, object]:
        reg = self.get(provider_id)
        return {
            "id": f"provider.{reg.provider_id}",
            "type": "ProviderDescriptor",
            "version": 1,
            "provider_id": reg.provider_id,
            "category": reg.category.value,
            "implementation": reg.implementation,
            "state": reg.state.value,
            "endpoint": reg.endpoint,
            "capabilities": reg.capabilities,
        }
