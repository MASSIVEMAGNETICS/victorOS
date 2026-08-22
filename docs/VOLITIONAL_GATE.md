# VictorOS Volitional Gate

**Status:** Canonical architecture specification  
**Invariant:** Automatic behavior is a proposal, never a consequential-action command.

## Purpose

The Volitional Gate converts observation into choice by suspending execution authority from the first generated policy long enough to evaluate alternatives.

```text
Choice = Alternatives + Inhibition + Evaluation + Authorization
```

The gate belongs between Victor's Experience/Emotion organs and the Choice Kernel. It controls the capability lease required for execution.

## Control flow

```text
EVENT
  -> EXPERIENCE FRAME
  -> AUTOMATIC POLICY PROPOSAL
  -> INDEPENDENT RISK SCORE
  -> AUTO_AUTHORIZED | DELIBERATION_REQUIRED
  -> ALTERNATIVES
  -> COUNTERFACTUAL EVALUATION
  -> CHOICE KERNEL
  -> ETHICA GOVERNOR
  -> CAPABILITY LEASE
  -> EXECUTION
  -> TRACE RECEIPT
  -> CHRONOS COMMIT
  -> LEARNING
```

## Hard invariants

1. No consequential action executes without authorization.
2. The proposing policy cannot calculate its own final risk classification.
3. Observations, inferences, feelings, predictions, and unknowns remain separate.
4. Doing nothing and gathering evidence are always representable candidate actions.
5. High arousal plus high irreversibility creates a temporal hold unless a bounded emergency policy applies.
6. Impulse and authorized choice are distinct state variables.
7. A single behavior does not rewrite identity.
8. Every deliberate decision produces a verifiable receipt.
9. Denied, deferred, and failed actions fail closed.
10. Genuine urgency selects a restricted emergency policy; it never restores unrestricted impulse execution.

## Experience frame

```json
{
  "observed": [],
  "inferred": [],
  "felt": [],
  "predicted": [],
  "unknown": []
}
```

Stories must not masquerade as observations.

## Deliberation score

```text
D = sigmoid(
    wE*E + wU*U + wI*I + wN*N + wC*C + wP*P
    - wR*R - wX*X
)
```

Where:

- E: emotional intensity
- U: uncertainty
- I: consequence magnitude
- N: novelty
- C: conflict between goals or models
- P: capability power
- R: reversibility
- X: genuine urgency
- sigmoid: bounded logistic function

If `D >= threshold`, deliberation is mandatory. Thresholds are policy-controlled and cannot be relaxed by the proposing subsystem.

## State machine

```text
PROPOSED
  -> RISK_SCORED
  -> AUTO_AUTHORIZED | DELIBERATION_REQUIRED
  -> ALTERNATIVES_GENERATED
  -> OUTCOMES_SIMULATED
  -> POLICY_CHECKED
  -> AUTHORIZED | DEFERRED | REJECTED
  -> EXECUTED
  -> VERIFIED
  -> LEARNED
```

Invalid transitions are rejected and recorded.

## Choice model

For each candidate action `a`:

```text
Q(a) =
    ExpectedReward
    - ExpectedHarm
    + GoalAlignment
    + InformationGain
    + Reversibility
    - ConstraintViolation
```

Minimum candidates for a deliberated decision:

- A0: do nothing yet
- A1: gather more evidence
- A2: ask or clarify directly
- A3: take a reversible action
- A4: execute the automatic proposal

The Choice Kernel selects among policy-valid candidates. Ethica may constrain or reject candidates but may not fabricate evidence.

## Temporal inhibition

For high-arousal, consequential, irreversible actions:

```text
delay = f(emotion, uncertainty, irreversibility, urgency)
```

During the hold, the capability lease remains unavailable. Emergency exceptions must use explicitly bounded capabilities and generate the same receipts as normal execution.

## Identity firewall

```text
Behavior at time t != Identity
```

Record: "Victor performed behavior X under state S." Identity updates require repeated, evidence-backed patterns under a separate governed process.

## Decision receipt

```json
{
  "observation": {},
  "initial_interpretation": {},
  "automatic_impulse": {},
  "risk_score": 0.0,
  "alternatives": [],
  "selected_action": {},
  "authorization": {},
  "expected_outcome": {},
  "actual_outcome": {},
  "prediction_error": 0.0,
  "trace_hash": ""
}
```

TRACE proves the decision path. Chronos commits the receipt. Learning may update prediction and proposal policies, but not constitutional constraints or authorization rules.

## Agency metric

```text
Agency =
    AlternativeGeneration
    * InhibitoryControl
    * CounterfactualEvaluation
    * GoalPersistence
    * ExecutionAuthority
```

If any factor approaches zero, agency approaches zero:

- no alternatives -> compulsion
- no inhibition -> impulse
- no evaluation -> randomness
- no persistent goals -> stimulus chasing
- no execution authority -> helplessness

## Acceptance criteria

- A high-impact irreversible proposal cannot execute without a capability lease.
- The automatic proposer cannot lower its independently calculated risk score.
- At least one non-intervention and one evidence-gathering action exist during deliberation.
- Emotional state affects scoring but never independently authorizes execution.
- Every terminal decision has a hash-linked TRACE/Chronos receipt.
- Restart preserves pending holds and prevents replay or bypass.
- Corrupt or missing authorization state fails closed.
- Tests cover low-stakes auto-authorization, mandatory deliberation, temporal hold, emergency restriction, rejection, restart recovery, and receipt verification.

## Canonical summary

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
