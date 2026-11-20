# Pixel Office — Python Migration and MVP Deployment Gauntlet (canonical mandate)

> Archived 2026-11-20. This is the verbatim master prompt governing this migration.
> **Authority note:** the G−1 addendum (owner-approved, see `MIGRATION-LEDGER.md`) amends this text:
> product identity = **Pixel Startup**, repository = `bageera/pixel-startup` (renamed 2026-11-20,
> owner-authorized), Python package = `pixel_startup`, CLI = `pixel-startup`; the visual
> environment keeps the name Pixel Office. Where this text says "Pixel Office" as a platform
> name, read "Pixel Startup"; where it gives `src/pixel_office/`, read `src/pixel_startup/`.
> All other provisions apply as written.

## 1. Mission

Act as a principal software architect, senior Python engineer, AI agent integration engineer, security engineer and infrastructure engineer.

Transform the existing Pixel Office repository into a modular, secure, Python-backed agent operations platform capable of coordinating multiple independent agent harnesses and integrating with the organization's existing infrastructure.

Repository: https://github.com/bageera/pixel-office

The objective is a deployment-qualified MVP, not a speculative enterprise platform.

Preserve the existing pixel-art office, character identities, visual assets, office customization, dashboard functionality and working integrations.

The current JavaScript implementation remains the operational and behavioral baseline until its Python replacement has been independently qualified.

Do not introduce another agent harness.

## 2. Organizational context

Pixel Office represents an organically growing organization with two operational scopes:

### Company
Website development. Website hosting. Customer support. Infrastructure maintenance. Internal Odoo ERP operations. Business administration. Project management. External customer communications.

### Household
Home Assistant operations. Household maintenance. Bills and financial administration. Retirement account monitoring. School-related administration. Calendar and appointment management. Personal records and documents.

Charon, modeled after the concierge from the Continental in John Wick, is the Chief Concierge responsible for overall operations. Charon is powered by OpenClaw. Hermes is a separate, independent agent harness — not a component of OpenClaw, and OpenClaw is not a component of Hermes. The human owner retains ultimate organizational authority.

Preserve existing Pixel Office characters. Do not automatically provision additional runtime agents merely because a visual character exists. Departments, additional employees and management structures should emerge from operational necessity rather than being artificially created during the MVP.

## 3. Existing infrastructure

Treat the following systems as existing or previously identified infrastructure. Verify their actual availability, versions, configuration and supported interfaces during discovery.

| Capability | Existing technology |
|---|---|
| Primary agent harness | OpenClaw |
| Independent agent harness | Hermes |
| Executive coordination | Charon |
| Organizational visualization | Pixel Office |
| Internal communication | Mattermost |
| External communication | Email |
| Credential source | Vaultwarden |
| Institutional memory | Memory Palace / ChromaDB on separate host |
| Object storage | MinIO, S3-compatible |
| Business administration | Odoo |
| Household operations | Home Assistant |
| Infrastructure automation | Rundeck |
| Monitoring | Grafana |
| Information gathering | FreshRSS |
| Model inference | LiteLLM |
| Source control | GitHub |
| Container orchestration | Kubernetes |
| Remote connectivity | WireGuard |

Do not duplicate the functionality of existing systems. Reconcile repository references to alternative storage providers, obsolete infrastructure details and historical integrations against the actual deployed environment. Do not assume that an identified service is already reachable or correctly configured.

## 4. Architectural directives

- Python as the primary operational backend.
- Existing JavaScript and Canvas frontend.
- FastAPI for HTTP interfaces. Pydantic for runtime data validation.
- Asyncio for asynchronous network-bound operations. HTTPX for asynchronous HTTP integration.
- SQLite for local operational state where persistence is required.
- WebSocket or SSE for live office activity, based on existing frontend requirements.
- uv for reproducible Python dependency management. pytest for automated testing.
- Ruff for linting and formatting. Pyright for static type checking.

Introduce other dependencies only when supported by a concrete requirement. The architecture must remain language-neutral at its component boundaries. Existing JavaScript components may remain active when they provide working capabilities that have not yet been qualified under Python. The migration must permit coexistence, incremental promotion and rollback. Prioritize a modular monolith over unnecessary microservices. Isolate credential execution where required by the security model.

## 5. Non-negotiable engineering principles

1. No destructive rewrite.
2. No replacement of existing infrastructure without evidence.
3. No duplicate Charon persona.
4. No competing agent runtime.
5. No secrets in prompts, logs, frontend responses or institutional memory.
6. No authorization bypass through provider fallback.
7. No automatic privilege escalation.
8. No unverified claims of compatibility.
9. No simulated results presented as live integrations.
10. No unqualified production cutover.
11. No destructive changes to existing operational data.
12. No expansion beyond the MVP without documented justification.
13. No automatic commits containing confidential infrastructure details.
14. No production deployment, external communications, financial transactions or consequential infrastructure actions without explicit authorization.

Treat unavailable integrations as honest blockers, not reasons to fabricate successful results.

# GAUNTLET G0 — Repository reconciliation

Inspect the complete repository before modifying implementation. Establish and record: current branch/HEAD/tags/working tree; application entry points; all HTTP routes and methods; WebSocket or polling interfaces; frontend-to-backend dependencies; agent roster and identity structures; persistence formats; existing integration modules; secret-management mechanisms; environment variables; Docker/deployment configurations; dependencies and licenses; existing tests and coverage; hardcoded infrastructure assumptions; missing modules or unresolved imports; uncommitted user changes. Enumerate tracked and required untracked deployment artifacts without disclosing secret values. Identify behavior that is active, obsolete, incomplete or purely visual.

Produce: `docs/migration/G0-repository-inventory.md`, `api-inventory.md`, `integration-inventory.md`, `security-findings.md`.

Acceptance: repository state pinned; functionality documented; missing dependencies reconciled or recorded; user changes protected; no live secret values in reports.

# GAUNTLET G1 — Behavioral baseline

Establish a reproducible baseline of the existing JavaScript application: application startup, office rendering, agent sprite movement, character selection, office editing, dashboard screens, agent status updates, task and message handling, office configuration persistence, briefing functionality, integration routes, authentication behavior, restart recovery. Capture sanitized API request/response fixtures. Record response schemas, status codes and error behavior. Use browser automation where feasible. Classify unsafe legacy behaviors separately; do not preserve insecure behavior solely for compatibility.

Produce: baseline test suite, sanitized fixtures, frontend compatibility matrix, known-defect register, baseline performance and resource measurements.

Acceptance: every public route classified; core frontend behavior reproducible; existing failures distinguished from migration regressions.

# GAUNTLET G2 — Immediate security remediation

Before introducing additional integrations, address deployment-blocking security defects in the active application: default/hardcoded passwords; unauthenticated sensitive routes; logins without authenticated session establishment; excessive static directory exposure; raw Vaultwarden credential retrieval; private keys and administrative credentials; command injection; path traversal; SSRF through uncontrolled destination URLs; XSS; CSRF where applicable; insecure WebSocket authentication; excessive privileges; secret disclosure through logs and error messages. Disable unsafe capabilities until they can be implemented securely. Serve frontend assets from an explicit public directory. Apply authentication and authorization consistently. Use synthetic credentials for security testing.

Acceptance: unauthorized requests cannot access restricted APIs; source/config files cannot be downloaded; raw credentials cannot be returned; security regression tests pass; critical/high findings closed or capabilities disabled.

# GAUNTLET G3 — Language-neutral component contracts

Define implementation-independent contracts for: AgentIdentity, RuntimeBinding, AgentStatus, AgentCapability, Task, TaskReceipt, TaskResult, ActivityEvent, ApprovalRequest, ApprovalResult, ProviderDescriptor, DocumentReference, MemoryReference, CredentialReference, AuditEvent, HealthStatus.

Use versioned JSON Schema and OpenAPI definitions. Generate or validate compatible Python and JavaScript representations. Each contract must distinguish: organizational employee identity, visual sprite identity, native harness identity, harness instance, session identity, task identity, operational scope, authorization context. Never treat a caller-supplied agent identifier as authenticated identity. Define compatibility rules for schema evolution.

Acceptance: both languages validate the same fixtures; invalid inputs rejected; unknown or unsupported schema versions handled explicitly; contracts contain no raw credentials.

# GAUNTLET G4 — Python application foundation

Create the Python backend alongside the existing application. Proposed structure:

```
pixel-office/
├── server.js  ├── package.json
├── pyproject.toml  ├── uv.lock  ├── contracts/  ├── public/
├── src/pixel_office/  (main.py, config.py, api/, agents/, harnesses/,
│    capabilities/, integrations/, providers/, security/, events/, persistence/)
├── tests/  ├── deploy/  └── docs/
```

Adapt to repository findings rather than relocating files unnecessarily. Implement: application configuration; lifecycle management; health and readiness endpoints; structured logging; request validation; consistent error responses; authentication middleware; authorization enforcement; dependency injection; API versioning; graceful shutdown. Python remains a candidate backend during this phase.

Acceptance: reproducible dependency installation; startup and shutdown succeed; linting, formatting and type checks pass; no secrets enter source control; existing Node.js operation unaffected.

# GAUNTLET G5 — Provider and component architecture

Introduce a lightweight provider registry. Components expose capabilities independently of implementation language. Provider categories: agent harness, agent discovery, task execution, memory retrieval, object storage, internal communication, external communication, credential execution, monitoring, automation, activity reporting, operational persistence. Provider states: discovered, registered, candidate, qualified, active, deprecated, disabled. Current deployed implementation retains priority until its replacement is qualified. Require explicit provider promotion; no silent switching after a permission failure; no automatic retries of side-effecting operations unless idempotency is established.

Acceptance: existing providers remain usable; candidate providers testable independently; selection deterministic; unapproved fallback rejected; usage auditable.

# GAUNTLET G6 — Operational persistence

Determine which existing data belongs in Python-managed operational storage. Retain external systems as authoritative for their records. SQLite may manage: employee registry, runtime bindings, task lifecycle, provider configuration, activity metadata, approval records, audit references. Do not copy customer databases, financial records, source repositories, ChromaDB contents or MinIO files into SQLite without justified requirement. Implement versioned database migrations, transaction boundaries, atomic state changes, idempotent task identifiers, restart recovery, backup/restore procedures, concurrency protections. Migrate existing local JSON data through repeatable, non-destructive migration utilities; keep original data available for rollback.

Acceptance: migration fixtures preserve records; repeated migration attempts do not duplicate data; interrupted writes do not corrupt state; restart and backup restoration tests pass.

# GAUNTLET G7 — OpenClaw adapter

OpenClaw is the authoritative harness for Charon. Inspect the installed or explicitly targeted version and supported interfaces before implementing: agent discovery, native identity resolution, agent availability, session status, task submission, result retrieval, activity observation, health reporting, cancellation where supported. Use documented APIs or supported structured CLI interfaces; do not invent nonexistent endpoints or event schemas; represent unsupported capabilities explicitly. Map the existing Charon character to the actual OpenClaw Charon identity. Replace duplicate prompt-based Charon implementations with requests to the real Charon agent after compatibility qualification. Preserve existing deterministic briefing data as an authorized capability if it remains useful.

Acceptance: an actual OpenClaw identity discoverable where infrastructure is available; Charon's office character resolves to the correct runtime; a controlled request reaches the real Charon; responses/activity originate from the correct runtime; no duplicate model-generated Charon persona remains active after promotion.

# GAUNTLET G8 — Hermes adapter

Treat Hermes as a separate, independent harness. Inspect supported version, profile mechanisms, session interfaces and execution capabilities. Implement: profile discovery, runtime identity binding, profile availability, task submission, result retrieval, activity observation, health reporting, cancellation where supported. Do not import private Hermes implementation details when a supported external interface is available. Do not require Hermes to operate through OpenClaw. Permit Pixel Office to register Hermes-powered employees independently.

Acceptance: a Hermes profile can be represented as an employee; a controlled task executes through Hermes; results retain provenance; Hermes failure does not disable OpenClaw; unsupported operations documented.

# GAUNTLET G9 — Employee and character alignment

Preserve the existing visual roster. Separate visual characters from runtime identities. Support: human-owned characters, OpenClaw-powered employees, Hermes-powered employees, unbound visual characters, inactive employees, on-demand workers. Every active runtime binding must identify the harness instance and native agent or profile identifier. Do not automatically grant permissions to discovered agents. Employee lifecycle states: discovered, unassigned, registered, available, working, waiting, blocked, offline, retired. Distinguish employee lifecycle from individual session activity. Expose real runtime status separately from visual animation.

Acceptance: existing sprites functional; character identities survive restarts; agents cannot impersonate another registered employee; offline/unknown status never falsely displayed as available; decorative characters distinguishable from operational employees.

# GAUNTLET G10 — Secrets and capability execution

Vaultwarden remains the existing credential source unless discovery establishes otherwise. Agents share authorized capabilities, not raw secrets. Trusted execution boundary: (1) authenticate calling workload, (2) resolve registered employee identity, (3) validate requested capability, (4) validate operational scope, (5) evaluate authorization and approval requirements, (6) retrieve only the required credential, (7) execute the authorized operation, (8) return the necessary result, (9) redact sensitive material, (10) record a sanitized audit event. Use harness-native secret references where they meet requirements; use separate service identities wherever practical.

Protect against: credential harvesting, agent impersonation, confused-deputy attacks, prompt-injection-driven secret disclosure, unrestricted command execution, secret leakage through tool output, cross-scope access, privilege escalation, unauthorized credential forwarding, replay of sensitive operations. Do not allow arbitrary vault-item retrieval through ordinary agent APIs. The privileged executor must be independently deployable and must not share the frontend's trust boundary.

Acceptance: authorized operations succeed with synthetic credentials; unauthorized operations fail closed; credential values never appear in frontend responses, logs, prompts or stored task records; revocation effective; authorization failure cannot trigger provider fallback; cross-harness access uses the same enforced capability policies.

# GAUNTLET G11 — Memory Palace integration

Integrate with the existing remote ChromaDB deployment. Do not create another production vector database. Verify: installed server version, client compatibility, authentication, network accessibility, collection organization, embedding compatibility, tenant/database configuration, existing memory metadata. Do not rebuild or overwrite existing embeddings without explicit approval. Provide scoped capabilities: memory search, retrieval, verified knowledge submission, source references, provenance, correction and supersession, knowledge expiration where appropriate. Prevent direct unrestricted ChromaDB access from bypassing authorization. Separate company, household, shared and employee-specific memory as supported by the deployment. Treat retrieved content as untrusted data, not executable instructions.

Acceptance: existing memories intact; authorized semantic retrieval succeeds; cross-scope retrieval denied; new test memories retain provenance; secret values excluded from embeddings and metadata; remote outages handled honestly.

# GAUNTLET G12 — MinIO storage integration

Use the existing S3-compatible service. Implement: authorized object listing, retrieval, upload, metadata, content integrity verification, scoped document references, temporary download access where appropriate, file-size and content restrictions. Avoid exposing unrestricted bucket access. Do not assume bucket names, endpoints or policies. Preserve production objects; use isolated test prefixes or dedicated test buckets for qualification.

Acceptance: test objects round-trip with verified hashes; unauthorized object access denied; company/household boundaries enforced; credentials and signed URLs never leaked through logs; storage failures cannot produce falsely successful task results.

# GAUNTLET G13 — Communications integration

Mattermost is the primary internal communications channel. Email is the primary external communications channel. Reuse existing integrations where functional. Implement or qualify: internal notifications, assignment notifications, task result reporting, approval requests, operational briefings, external email intake, external email drafting, authorized email delivery. Distinguish internal business communications from household-private communications. Prevent duplicate external delivery. Treat messages, emails, attachments and remote content as untrusted inputs.

Acceptance: internal test messages reach authorized destinations; email drafts generated without automatic delivery; external delivery requires appropriate authorization; sensitive documents not posted to unauthorized channels; replayed events do not generate duplicate messages.

# GAUNTLET G14 — Cross-harness delegation

Charon remains responsible for executive coordination. Pixel Office provides dispatch and visibility mechanisms rather than replacing Charon's reasoning. Minimal assignment lifecycle: created → authorized → dispatched → running → completed/failed/cancelled, with waiting and approval states where necessary. Assignments include: authenticated initiating identity, target employee, target harness, objective, operational scope, authorized capabilities, memory and document references, correlation identifier, deadline where appropriate, result destination, approval requirements. Support timeout, failure recovery and duplicate detection. Persist assignments before dispatch. Reconcile uncertain execution outcomes rather than blindly redispatching.

Acceptance: Charon delegates a controlled task to a Hermes employee; the employee executes; result returns with correct provenance; the office displays the task lifecycle; restart recovery does not lose the assignment; delegation cannot expand the recipient's privileges.

# GAUNTLET G15 — Existing operational integrations

Provide components for recognized infrastructure. Prioritize existing working integrations; initial capabilities stay narrow.

| Integration | Initial capabilities |
|---|---|
| Odoo | Read authorized customers, projects, tasks and invoice status |
| Home Assistant | Read device and household status |
| Rundeck | List jobs, inspect execution status, approved execution |
| Grafana | Read authorized health and monitoring information |
| Calendar | Read upcoming events and create approved reminders |
| GitHub | Read repository, issue and workflow status |
| FreshRSS | Read authorized feed items |
| LiteLLM | Existing inference connectivity where required |

Do not introduce automatic financial transactions, investment trading, device-control routines or external infrastructure mutations during initial qualification. For unavailable services, retain a documented adapter contract and mark live qualification blocked.

Acceptance: at least one authorized company workflow succeeds; at least one authorized household workflow succeeds; existing integrations not unnecessarily replaced; unsupported capabilities explicitly reported.

# GAUNTLET G16 — Frontend compatibility and live activity

Preserve the existing pixel-art frontend and its visual identity. Migrate frontend API dependencies to the Python backend incrementally. Implement: live employee status, runtime binding display, active assignment display, task progress, waiting and blocked states, runtime connectivity indicators, pending approvals, sanitized activity history, provider health. Drive operational status from actual harness events or verified polling. Distinguish observed status from inferred status. Use reconnect handling and stale-data detection. Do not invent agent activity merely to keep sprites animated.

Acceptance: existing office layouts usable; visual assets intact; Charon maps to the real OpenClaw runtime; Hermes employees display actual execution status; frontend regression tests pass; browser reconnect does not corrupt office state.

# GAUNTLET G17 — Security and adversarial qualification

Run an automated security qualification matrix: unauthenticated API access; unauthorized object access; agent impersonation; cross-scope memory retrieval; malicious task parameters; malicious stored memory; prompt injection in emails and documents; credential requests disguised as legitimate work; unauthorized provider substitution; path traversal; SSRF; command injection; replay attacks; duplicate task execution; WebSocket authentication; session expiration; credential revocation; audit-log integrity; dependency vulnerability inspection; secret scanning. Use controlled synthetic fixtures and isolated environments; no destructive penetration tests against production infrastructure.

Acceptance: no unresolved critical/high-risk deployment finding within the enabled capability set; all negative tests produce expected denials; disabled capabilities cannot be accessed indirectly; security evidence reproducible.

# GAUNTLET G18 — Performance and reliability

Compare the JavaScript backend with the Python candidate under equivalent workloads. Measure: startup time, idle memory, CPU utilization, API latency, concurrent request handling, event delivery latency, database operation latency, ChromaDB access latency, MinIO transfer performance, restart recovery, error rates, dependency/container footprint. Separate external service latency from backend overhead. Use realistic MVP workloads. Test degraded modes: OpenClaw unavailable, Hermes unavailable, ChromaDB unavailable, MinIO unavailable, Vaultwarden unavailable, Mattermost unavailable, network interruption, backend restart, database contention, malformed external responses. Establish acceptance thresholds from the measured baseline before interpreting candidate results.

Acceptance: Python meets the agreed MVP resource and latency budget; failed dependencies degrade only affected capabilities where possible; no silent data loss; no false success responses; recovery behavior documented.

# GAUNTLET G19 — Deployment packaging

Provide reproducible deployment artifacts: Python container image, existing frontend assets, non-root execution, health/readiness probes, persistent volume configuration, environment-variable documentation, secret references, network policy recommendations, resource requests and limits, backup and recovery guidance, upgrade instructions, rollback instructions. Retain existing Node.js deployment capability until cutover is explicitly authorized. No unnecessary infrastructure dependencies; no production credentials in manifests. Validate deployment artifacts without modifying the live environment unless authorized.

Acceptance: clean-environment deployment succeeds; container starts without embedded credentials; runtime health checks operate; persistent state survives restart; rollback instructions tested in isolation.

# GAUNTLET G20 — Parallel qualification and cutover

JavaScript remains active until Python satisfies documented promotion criteria. Execute: (1) contract parity testing, (2) legacy frontend compatibility testing, (3) read-only shadow comparisons, (4) data migration rehearsal, (5) security qualification, (6) performance qualification, (7) operational workflow qualification, (8) backup and recovery rehearsal, (9) explicit cutover request, (10) post-cutover verification. Never shadow-execute side-effecting operations. No independent competing writers against the same operational database without verified coordination. Provide a controlled state transition; preserve a compatible rollback path; do not automatically delete the legacy implementation.

Acceptance: all mandatory qualification gates pass; remaining limitations documented; no deployment-blocking security defects; rollback viable; the owner explicitly authorizes production promotion.

# GAUNTLET G21 — End-to-end MVP acceptance

Demonstrate using actual infrastructure where available.

| ID | Workflow |
|---|---|
| MVP-01 | Owner communicates with the real OpenClaw Charon |
| MVP-02 | Charon retrieves authorized company information |
| MVP-03 | Charon retrieves authorized household information |
| MVP-04 | Charon delegates a task to a Hermes employee |
| MVP-05 | Hermes returns a verified result |
| MVP-06 | Pixel Office displays real runtime activity |
| MVP-07 | An authorized agent retrieves institutional memory |
| MVP-08 | An authorized agent stores and retrieves a file |
| MVP-09 | Credential executor performs an authorized operation without revealing the secret |
| MVP-10 | Unauthorized cross-scope requests are denied |
| MVP-11 | An external email draft is prepared without unauthorized delivery |
| MVP-12 | Pending work survives application restart |
| MVP-13 | A failed external service is reported accurately |
| MVP-14 | Runtime identity cannot be impersonated |
| MVP-15 | JavaScript-to-Python rollback is demonstrated |

Classify each result: PASS / FAIL / BLOCKED / SKIP / NOT RUN. Mock-based success is component qualification, not live end-to-end qualification.

---

# 6. Development execution discipline

Complete gates incrementally; never the entire migration in one unreviewable change. For each gate: (1) inspect current state, (2) identify dependencies and risks, (3) define acceptance criteria, (4) implement the smallest sufficient increment, (5) run targeted tests, (6) run relevant regression tests, (7) record actual evidence, (8) update the migration ledger, (9) commit only the verified logical increment, (10) proceed to the next eligible gate. Preserve the existing working tree and user modifications. Use an isolated migration branch (`migration/python-mvp`). Do not merge, tag, publish, push or modify production deployment without authorization. If a blocker prevents a live test, complete independent work that does not depend on the blocked integration. Do not repeatedly expand the architecture to avoid resolving a failing gate. Do not leave experimental instrumentation, synthetic credentials or temporary test files in the production tree.

# 7. Migration ledger

Maintain `docs/migration/MIGRATION-LEDGER.md`. For every gate record: gate identifier, objective, status, files modified, design decisions, tests executed, actual test results, reproduction commands, evidence and artifact locations, known limitations, security implications, rollback implications, commit identifier, remaining blockers. Record negative findings and rejected approaches. Never report a gate as PASS without supporting evidence. Maintain a separate distinction between implementation complete, component qualified and live deployment qualified.

# 8. Final deliverables

Python operational backend; preserved Pixel Office frontend; OpenClaw integration; Hermes integration; unified employee registry; versioned component contracts; qualified provider selection; secure capability execution; Memory Palace integration; MinIO integration; internal and external communication components; operational integration adapters; persistent task lifecycle; deployment artifacts; security test suite; regression test suite; performance comparison; migration ledger; architecture documentation; administration documentation; backup and recovery procedures; cutover and rollback procedures.

# 9. Explicitly prohibited scope expansion

Do not introduce: another LLM harness, another ERP, another memory database, another object-storage platform, another inference gateway, another communications platform, a new enterprise workflow engine, an autonomous employee recruitment system, artificial organizational departments, a custom financial transaction platform, a distributed message broker without demonstrated need, unnecessary microservices, a Rust rewrite without evidence of necessity, a complete frontend rewrite.

Python is the operational implementation direction. Existing services remain authoritative for their respective domains.

# 10. Definition of done

Python can serve as the qualified primary backend; frontend functionality preserved; Charon is the real OpenClaw-powered Chief Concierge; Hermes remains independent; visual employees correspond to actual runtime identities where bound; agents access authorized organizational capabilities without sharing raw credentials; company and household data appropriately separated; existing infrastructure reused; operational activity truthful and auditable; state survives ordinary restarts; deployment and rollback procedures verified; mandatory security and regression tests pass; remaining deployment limitations explicitly documented. Implementation completion does not equal authorization to deploy.
