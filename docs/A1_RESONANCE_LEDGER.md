# A1-RL-001 — Resonance Ledger / Signal Seed Analyzer

**Status:** executable prototype, non-canonical subsystem  
**Scope:** episodic memory, provenance, cross-domain recurrence, contradiction preservation, structural resonance analysis  
**Canonical boundary:** A1 does **not** replace Chronos and does not write the canonical Victor identity/state head.

## Why A1 exists

Victor's frozen architecture genealogy already defines the conversation unit as an **episode**, requires append-only history, and separates authoritative history from derived graph/world-model projections. A1 operationalizes the missing analysis seam: preserve source episodes, bind observations to evidence spans, map concept relations, and calculate which structures persist across time and domains.

The Chladni/cymatics language is an analogy for structural persistence. A1 makes no acoustic, supernatural, consciousness, precognition, or semantic-truth claim from resonance alone.

## Non-negotiable epistemic rule

```text
Resonance != Truth
```

A concept can be historically central and factually unsupported. A1 stores recurrence/centrality and evidence quality as separate dimensions.

## Data flow

```text
RAW SOURCE
  -> SHA-256 preservation
  -> source record
  -> explicit or heuristic observations
  -> concept/alias resolution
  -> provenance-aware graph edges
  -> resonance vector
  -> classification
  -> integrity verification
```

The local event log is hash-linked. It is an A1 receipt chain only. Promotion into Chronos requires a separate adapter and verification receipt.

## Resonance vector

For concept `x`:

```text
X = [P, D, C, E, V, K]
```

- `P` persistence: recurrence across independent sources
- `D` domain diversity: cross-domain presence
- `C` graph centrality: relationship degree relative to the current graph
- `E` evidence quality: evidence-state weight multiplied by observation confidence
- `V` volatility: interpretation-state change plus contradiction pressure
- `K` contradiction pressure: explicit contradiction/supersession/invalidity pressure

Base score:

```text
R = P * D * C * E
```

Classification does not canonize anything:

- high `R`, low `V`, **>=3 independent sources** -> `NODAL_INVARIANT_CANDIDATE`
- high `R`, high `V`, **>=2 independent sources** -> `ACTIVE_RESONANT_MODE`
- high contradiction pressure -> `CONTRADICTION_PRESSURE`
- weak/single-source structures -> `EXPERIMENT` or `DORMANT_OR_INCIDENTAL`

## Heuristic extraction boundary

`resonance extract` is deliberately deterministic and conservative. It extracts candidate phrases from a source and stores them as:

```text
evidence_state = EXTRACTED
interpretation_state = heuristic_candidate
confidence = 0.55
```

It never labels heuristic extraction as verified truth. Human or verifier-backed observations should be added with `resonance observe`.

## CLI

```bash
# Ingest a complete episode or artifact
python resonance.py ingest episode.txt \
  --type episode \
  --title "2026-08-30 Chladni/A1 episode" \
  --domain VictorOS \
  --domain music \
  --author human

# Candidate extraction
python resonance.py extract SRC-... --max 25

# Bind an explicit evidence observation
python resonance.py observe provenance SRC-... \
  --span "Canonical state changes require provenance." \
  --confidence 1.0 \
  --evidence-state VERIFIED

# Link concepts
python resonance.py link provenance SUPPORTS continuity --confidence 1.0 --status verified

# Scan
python resonance.py scan
python resonance.py scan --json

# Reconstruct one concept's history
python resonance.py history provenance

# Verify source hashes + A1 event chain + foreign keys
python resonance.py verify
```

Default DB:

```text
.victor/resonance.db
```

## Canonical substrate mapping

A1 is designed to plug into, not fork, the frozen substrate:

```text
TRACE-0 -> INFORMATRON -> CHRONOS -> REDUCER -> ROGRAPH/WORLD MODEL
                         ^
                         |
              future verified adapter
                         |
                       A1-RL
```

Near-term role:

- raw episode/artifact preservation
- evidence-span binding
- concept recurrence analysis
- contradiction surfacing
- cross-domain invariant discovery
- candidate transition material for later canonical review

## Failure modes and defenses

### False resonance
Repeated discussion can make a concept structurally important without making it true.

**Defense:** `E` remains independent from recurrence and `Resonance != Truth` is enforced in tests.

### Semantic alias duplication
Different spellings can fragment one concept.

**Defense:** deterministic normalization plus explicit `alias` command. No unverified semantic auto-merge.

### Hallucinated lineage
An extractor could invent relationships.

**Defense:** extraction creates observations only. Edges are explicit operations with status/confidence and optional source binding.

### Historical rewriting
Mutable summaries could erase earlier states.

**Defense:** no delete command, source hashes, append-only event receipts, explicit contradiction edges.

### Competing truth store
A local prototype could accidentally be treated as canonical identity state.

**Defense:** code/docstrings/docs state that A1 is non-canonical until a separately verified Chronos adapter exists.

## Acceptance tests

The test suite verifies:

1. source hashes and event-chain integrity
2. exact duplicate source deduplication
3. heuristic extraction never claims verified truth
4. repeated cross-domain evidence can form an invariant candidate
5. high recurrence does not override weak/disputed evidence
6. contradictions remain explicit
7. source tampering is detected
8. event-chain tampering is detected
9. history reconstruction returns source provenance
10. a single source cannot self-promote into an invariant

Run:

```bash
python -m pytest tests/test_resonance_ledger.py -q
```

## Next integration gate

Do **not** merge A1 directly into Chronos merely because the tests pass.

The next canonical integration step is a one-way adapter that emits a candidate `ExperienceTransition` containing A1's verified source/observation/edge receipts. Chronos should accept that candidate only through its existing authority and verification gates.
