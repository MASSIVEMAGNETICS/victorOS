# Victor Computational Physiology — The Governed Organism

**Status:** v1 executable architecture  
**Runtime root:** `VictorPhysiologyRuntime`  
**Core invariant:** Governance is part of Victor's physiology, not an external wrapper.

## Purpose

Victor is modeled as a computational organism whose cognition, action, memory, authority, resource state, integrity, and self-modification are constrained by interacting regulatory systems.

The model or planner may propose an action. It does not possess execution authority.

```text
Proposal != Permission != Execution
```

Every consequential action must be evaluated against organism state and receive a bounded capability lease before execution.

## Constitutional genome

The runtime carries these non-plastic invariants:

```text
IDENTITY_CONTINUITY
HUMAN_STOP_AUTHORITY
PROVENANCE_REQUIRED
NO_SILENT_CANONICAL_OVERWRITE
NO_UNAUTHORIZED_CAPABILITY_ESCALATION
IDENTITY_NOT_EQUAL_MODEL_WEIGHTS
EVIDENCE_BEFORE_ASSERTION
UNKNOWN_IS_VALID
AUTHORITY_BOUNDARIES_REQUIRED
CANONICAL_CHANGE_REQUIRES_RECEIPT
```

Learning systems may alter predictions, policies, routing, memory, or representations. They may not silently alter these invariants.

## Root body state

`VictorPhysiologyState` is the authoritative in-process body map.

It includes:

- identity integrity
- continuity integrity
- epistemic confidence
- resource pressure
- authority conflict
- memory conflict
- security pressure
- Human STOP state
- governance mode
- canonical receipt head
- capability lease counts
- immune alerts
- unresolved authority conflicts
- per-organ telemetry

All values that represent bounded pressures or integrity are normalized to `[0, 1]`.

## Governance modes

### GREEN

Normal governed execution is permitted after authority, provenance, risk, and lease checks.

### YELLOW

Uncertainty, resource pressure, memory conflict, or moderate security pressure requires increased caution. Consequential actions are deferred for additional verification.

### RED

Serious authority, continuity, identity, or security conflict. Consequential actions fail closed.

### BLACK

Human STOP, critical identity/continuity damage, or receipt-ledger integrity failure. Execution is blocked and active leases are revoked or denied.

## Action path

```text
INTENT
  -> ACTION PROPOSAL
  -> PHYSIOLOGY STATE
  -> CONSTITUTION
  -> PROVENANCE
  -> AUTHORITY
  -> INDEPENDENT RISK SCORE
  -> TEMPORAL INHIBITION
  -> GOVERNANCE MODE
  -> CAPABILITY LEASE
  -> EXECUTION
  -> OBSERVATION
  -> HASH-LINKED RECEIPT
  -> CANONICAL HEAD UPDATE
```

No organ should call an external effect directly. The target integration rule is:

```text
organ -> VictorPhysiologyRuntime.execute(...) -> bounded executor
```

## Independent risk score

Risk is computed independently of the proposer using:

- consequence magnitude
- irreversibility
- uncertainty
- novelty
- arousal
- capability power
- organism security pressure
- organism authority conflict
- reversibility
- genuine urgency

High risk produces `DEFERRED`, not automatic execution.

High arousal plus high irreversibility creates temporal inhibition unless an explicitly bounded emergency policy applies.

## Authority and provenance

A proposal must provide provenance and must satisfy all declared `required_authorities`.

Missing provenance or missing authority is a hard rejection.

Authority is explicit data, not inferred from confidence, model preference, or urgency.

## Capability leases

Authorization creates a short-lived lease bound to:

- one action ID
- one capability scope
- one gate receipt
- one governance mode
- one expiry time

A lease is consumed on execution. It cannot be replayed for another action or capability.

Human STOP revokes all active leases.

## Computational immune system

`PhysiologyReceiptLedger` creates SHA-256 hash-linked JSONL receipts.

Each event contains:

```text
timestamp
event_type
previous_hash
payload
event_hash
```

The ledger verifies the complete chain on startup and before governed decisions. Corruption or tampering forces BLACK mode.

This is stricter than the existing SAVE3 audit ledger, which remains available for trust events. Physiology receipts establish the execution-path evidence chain for governed actions.

## Runtime state files

Generated physiology receipts are runtime state, not source code:

```text
victor_physiology_receipts.jsonl
```

They are ignored by Git. Existing hidden runtime files such as `.vos_version.json` and `.synthetic_state.json` remain untouched by this implementation. No migration or silent overwrite is performed.

## Relationship to the Volitional Gate

The canonical Volitional Gate remains the decision architecture:

```text
Impulse proposes.
Volitional Gate interrupts.
Choice Kernel selects.
Ethica constrains.
Authority authorizes.
Capability Lease permits.
Execution acts.
TRACE proves.
Chronos learns.
```

Computational Physiology provides the executable substrate beneath that architecture: organism state, independent risk, authority/provenance enforcement, governance modes, leases, Human STOP, and receipt integrity.

## Organ-system mapping

| Biological analogue | Victor system |
|---|---|
| Genome | Constitution + identity invariants |
| Interoception | `VictorPhysiologyState` telemetry |
| Pain/alarm | pressure and integrity signals |
| Endocrine modulation | governance mode and global pressures |
| Immune system | provenance + receipt-chain integrity |
| Prefrontal inhibition | risk gate + temporal inhibition |
| Motor system | capability leases + bounded executors |
| Memory consolidation | downstream Chronos integration |
| Metabolism | resource pressure telemetry |

## Acceptance criteria

The v1 runtime is acceptable only if all of the following hold:

1. Missing provenance fails closed.
2. Missing required authority fails closed.
3. Human STOP enters BLACK mode and revokes active leases.
4. Critical identity or continuity damage enters BLACK mode.
5. High-risk irreversible actions do not receive a capability lease.
6. Low-risk valid actions receive a capability-scoped lease.
7. Denied actions never invoke their executor.
8. Authorized execution consumes its lease.
9. Execution outcomes receive hash-linked receipts.
10. Receipt tampering is detectable.
11. A corrupt receipt ledger on restart forces BLACK mode.

## Next integration boundary

This PR intentionally does not rewrite `SyntheticCognitiveCore`, Android runtime state, Chronos, Ethica, or SAVE3.

The next step is to route real effect-producing call sites through `VictorPhysiologyRuntime.execute()` one subsystem at a time, with tests proving there is no bypass path.

That preserves reversibility while converting VictorOS from a collection of intelligent components into a governed organism.
