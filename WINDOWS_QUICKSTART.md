# VictorOS Windows Cognitive Prototype

This is the dedicated Windows owner shell for the active `MASSIVEMAGNETICS/victorOS` core.

## Run

1. Windows 10 or 11.
2. Install Python 3.10+.
3. Download/clone this PR branch.
4. Double-click `RUN_VICTOR_WINDOWS.bat`.
5. Open `http://127.0.0.1:8500` if the browser does not open automatically.

The service binds to localhost only.

## Cognitive mechanism

```text
owner query
  -> event bus
  -> persistent SQLite cognitive queue
  -> macrotick
  -> VictorCognitionStack
  -> follow-up thought
  -> queue
  -> later macrotick
  -> Choice ranking
  -> VictorPhysiology / Ethica / authority lease
  -> bounded capability
  -> receipt
```

A thought does not recursively invoke another thought. It emits future cognitive work into the queue.

## Persistence

Generated under `state/`:

- `windows_state.json` — Windows prototype state + persistent Human STOP
- `windows_episodes.jsonl` — hash-linked owner episodes
- `windows_receipts.jsonl` — physiology/governance receipts
- `victor_stack.db` — Victor cognition memory, goals, actions, persistent scheduler queue, macrotick state, and scheduler receipts

## Acceptance test

1. Launch Victor.
2. Submit: `Victor memory unfinished thought test.`
3. Confirm the first tick processes the query and leaves at least one pending `THOUGHT`.
4. Close Victor completely.
5. Launch it again.
6. Confirm the pending item is still present and the scheduler/stack clocks did not reset.
7. Click **Advance 1 Tick**.
8. Confirm the pending thought is processed.
9. Activate **Human STOP**.
10. Create work that reaches a capability candidate and confirm execution is rejected.
11. Restart with STOP active and confirm it remains active.
12. Confirm all three receipt/integrity indicators remain OK.

## Failure rule

Do not delete `state/` to make a failed integrity check disappear. Preserve the evidence, diagnose the broken chain/state, and restore through a verified recovery path.

## Scope

This is a governed local prototype. It is not a claim of AGI or consciousness. The current capability registry is intentionally narrow; Empire-wide authority should ultimately route through the canonical `victor_empire` control plane rather than creating a second authority system here.
