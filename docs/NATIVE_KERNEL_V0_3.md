# Victor Native Kernel v0.3

**Status:** integration candidate  
**Runtime:** `vos_core.native_kernel.NativeKernel`  
**Invariant:** resonance coordinates candidate cognition; it does not decide truth.

## Purpose

Native Kernel v0.3 integrates the existing deterministic cognitive stack, A1
evidence/resonance ledger, and governed physiology runtime into one episode-
scoped loop without creating a parallel canonical truth store.

```text
observation
  -> EPISODE
  -> CONTENT OBJECT
  -> A1 SOURCE / OBSERVATION
  -> NATIVE ORGAN STACK
  -> EPISODE/TICK/CONCEPT MEMBRANE
  -> CANDIDATE GESTALT
  -> EXPLICIT VERIFICATION
  -> ExperienceTransitionCandidate
  -> ChronosPromotionAdapter
  -> canonical Chronos implementation
```

External effects use the existing physiology path:

```text
KernelActionCandidate
  -> ActionProposal
  -> VictorPhysiologyRuntime
  -> constitutional / authority / risk checks
  -> bounded capability lease
  -> executor
  -> physiology receipt
  -> native-kernel receipt
```

## What this fixes

### Episode identity is separate from content identity

The same text can occur in multiple experiences. Native Kernel stores the text
once in `content_objects` but records every occurrence as a separate `episodes`
row.

```text
content identity != episode identity
```

### Legacy global membrane is disabled on this path

`NativeOrganStack` subclasses `VictorCognitionStack` and disables the legacy
global resonance/crystallization mechanism while keeping its deterministic
memory, attention, association, rule inference, goals, planning, and audit
functions.

No legacy `emergent_gestalt` is produced by `NativeKernel.run_episode()`.

### Resonance is scoped

Organ signals are unique inside:

```text
(episode_id, tick, concept_id, organ, event)
```

Signals from different episodes or ticks cannot accumulate into one gestalt.

### Gestalts are candidates, not facts

A quorum of independent organ pathways creates a `CANDIDATE` gestalt only.
The record explicitly carries `canonical = false`.

Promotion requires a separate verification receipt.

### No fake Chronos

Native Kernel does not claim to be Chronos and does not fabricate a canonical
head. A verified transition becomes `VERIFIED_CANDIDATE` and can only be
promoted through an injected `ChronosPromotionAdapter`.

An adapter claiming acceptance must return both:

- `chronos_receipt_hash`
- `chronos_head`

Otherwise the promotion fails.

## Runtime components

### `Episode`

Durable occurrence record containing:

- episode ID
- content hash
- source
- tick
- concept ID
- A1 source ID
- prior native-kernel receipt head
- lifecycle state

### `OrganSignal`

Typed organ output carrying:

- episode/tick/concept scope
- organ
- event
- payload
- confidence
- evidence state

### `CandidateGestalt`

Deterministically assembled from sorted signals after the configured organ
quorum is reached.

### `ExperienceTransitionCandidate`

Produced only after explicit verification. It contains the observation hash,
gestalt hash, verification receipt hash, and optional expected prior Chronos
head.

It is not canonical by itself.

### `KernelActionCandidate`

A proposed effect. It has no authority. Execution is delegated to
`VictorPhysiologyRuntime`.

## Receipt integrity

Native Kernel maintains a separate SHA-256 hash-linked integration receipt
chain. It records:

- episode opening
- organ signals
- candidate gestalt updates
- verification
- transition-candidate creation
- Chronos promotion results
- action decisions

This receipt chain is an integration evidence chain, not the canonical Chronos
identity/state head.

## Acceptance tests

`tests/test_native_kernel.py` verifies:

1. identical content creates distinct episodes
2. content storage remains deduplicated
3. no legacy crystallization is emitted
4. membrane state cannot combine across episodes/ticks
5. quorum produces a candidate, not canonical truth
6. verification requires a named verifier and evidence references
7. rejected candidates cannot create transition candidates
8. verified candidates remain explicitly non-canonical
9. Chronos acceptance requires a receipt and resulting head
10. Human STOP blocks effect execution
11. kernel receipt tampering is detected
12. A1 remains separate and its evidence chain verifies

Run:

```bash
python -m pytest tests/test_native_kernel.py -q
python -m pytest tests/ -q
```

## Deliberate limits

v0.3 does **not** claim:

- general reasoning
- scientific emergence
- canonical Chronos integration
- autonomous self-modification
- semantic concept equivalence
- learned causal inference
- unrestricted execution

The next promotion gate is a real, independently verified one-way Chronos
adapter against the canonical runtime implementation.
