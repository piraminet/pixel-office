# Pixel Startup — component contracts (G3)

Language-neutral data contracts for the migration (mandate: `docs/migration/MANDATE.md`,
gate G3). Each schema is the source of truth for its contract; this directory is
versioned independently of the JS and Python implementations.

## Contents

- `schemas/*.schema.json` — 16 contracts, JSON Schema Draft 2020-12, envelope fields
  `id`, `type` (const of the contract name), `version` (const 1).
- `openapi.json` — OpenAPI 3.1 document exposing every schema as a component (HTTP
  payload design reference; schemas remain the source of truth).

## Validators (parity proof)

`node tests/contracts/validate_contracts.js` — zero-dependency subset validator.
`python3 tests/contracts/validate_contracts.py` — uses the `jsonschema` library
(Draft 2020-12) when importable, else falls back to the identical hand-rolled
subset implementation. Both must accept every `tests/contracts/fixtures/valid/`
fixture and reject every `tests/contracts/fixtures/invalid/` fixture.

Subset semantics shared by both hand-rolled validators: `type` (incl. unions with
`null`), `const`, `enum`, `pattern`, `minLength`, `minimum`, `minItems`, `required`,
`additionalProperties: false`, nested `properties`. **Schemas must stay inside this
subset** — that is what guarantees subset↔jsonschema parity; expanding beyond it
requires promoting the JS validator (ajv, new dependency — requires owner sign-off
per the "no new deps without concrete requirement" rule).

## Schema evolution rules (C3.6)

1. `version` is a bare `const`. Callers must handle an unknown version as an
   explicit error (const mismatch) — never silently reinterpret. HTTP layers map
   this to an explicit 4xx, never to a silent fallback.
2. **Additive, non-breaking change without a version bump:** adding an OPTIONAL
   property (or widening an unvalidated field) is permitted; old validators ignore
   it under `additionalProperties: false` semantics only if the property is added
   to the schema — older deployed validators with the older schema reject unknown
   keys, so cross-version tolerance must be verified through the fixture suite
   before deployment, and the change announced in the ledger.
3. **Breaking change (new required field, changed enum/const, narrowed type,
   removed/renamed field):** requires a version bump — a NEW schema file with the
   incremented `version` const and a new `$id`, with the old file retained for
   the coexistence window. Both language validators must run against both
   versions during the transition.
4. `type` const is immutable: a contract never changes meaning under the same
   name; a different meaning takes a new contract name and a ledger record.
5. Fixture discipline: every accepted/rejected fixture set in
   `tests/contracts/fixtures/` is contractual evidence; extend it for every
   evolution step before shipping it.

## Credential hygiene (C3.7)

No schema or fixture may carry a value-bearing credential key (checked
automatically by both validators: `secret|password|api_key|private_key|token_value|
bearer|credential_value|client_secret`). `CredentialReference` deliberately holds
only identifiers and policy fields — credential values travel solely through the
G10 trusted execution boundary.

## Agent identity separations (C3.4/C3.5)

`AgentIdentity` requires eight distinct fields so the eight identity layers can
never collapse into one another: `employee_id` (organizational), `sprite_id`
(visual), `native_harness_id` (native harness), `harness_instance_id` (harness
instance), `session_id` (session), `current_task_id` (task), `operational_scope`
(scope), `authorization_context` (authorization). Caller-supplied `asserted_id` is
required alongside a distinct `verified_binding` object (nullable for unbound
visual characters) — a caller-supplied identifier is never treated as an
authenticated identity.
