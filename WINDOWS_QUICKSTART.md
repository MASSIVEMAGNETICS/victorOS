# VictorOS Windows Prototype

This is the dedicated Windows owner shell for the active `MASSIVEMAGNETICS/victorOS` core.

## Run it

1. Use Windows 10 or 11 with Python 3.10+ installed.
2. Download or clone this repository.
3. Double-click `RUN_VICTOR_WINDOWS.bat`.
4. Victor creates an isolated `.venv`, installs the pinned requirements, opens `http://127.0.0.1:8500`, and boots the local prototype.

No cloud API key is required. The server binds to `127.0.0.1` only.

## What is real in this prototype

- Persistent local state in `state/windows_state.json`.
- Persistent owner episodes in `state/windows_episodes.jsonl`.
- SHA-256 hash-linked episode integrity verification.
- Existing `VictorPhysiologyRuntime` constitutional gates and capability leases.
- Existing SHA-256 physiology receipt ledger in `state/windows_receipts.jsonl`.
- Explicit Human STOP; when active, the physiology runtime rejects governed execution.
- Human STOP survives a Windows prototype restart through the state file.
- Corrupt episode/state evidence causes fail-closed behavior rather than silent repair.

## What this does **not** claim

This is a governed prototype shell, not evidence of AGI, consciousness, autonomous general intelligence, or a finished operating system. The current local synthetic core performs bounded deterministic cognition/routing and emits structured cognitive telemetry.

## Acceptance test

1. Double-click `RUN_VICTOR_WINDOWS.bat`.
2. Confirm the browser opens the Windows prototype.
3. Commit an owner input and verify an episode plus receipt appears.
4. Close the terminal and run the batch file again; confirm boot/episode counts persist.
5. Activate Human STOP; confirm input is disabled and governance becomes `BLACK`.
6. Close and restart; confirm Human STOP is still active.
7. Explicitly reset Human STOP; confirm processing resumes only after the reset.
8. Verify `state/windows_episodes.jsonl` and `state/windows_receipts.jsonl` remain intact.

## Recovery rule

Do **not** delete the `state/` directory to bypass an integrity fault. Preserve the evidence first, diagnose the corrupt ledger/state, and restore from a known-good copy or a verified migration path.
