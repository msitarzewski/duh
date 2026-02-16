# How Consensus Works

## The problem

Every LLM has blind spots. A single model gives you one perspective with no way to know what it missed, oversimplified, or got wrong. Self-critique helps, but models are biased toward agreeing with themselves.

## The solution: forced disagreement

duh uses a 4-phase protocol that forces genuine disagreement between models. The key insight: a challenged and revised answer is consistently stronger than a direct answer from any single model.

## The 4 phases

### 1. PROPOSE

The strongest available model (selected by output cost as a capability proxy) generates an initial answer.

The proposer gets a system prompt that encourages thorough, specific answers with concrete examples and numbers. No hedging.

```
IDLE  -->  PROPOSE
```

### 2. CHALLENGE

Multiple challenger models (default: 2) receive the proposal with explicit instructions to **disagree**:

- They must find at least one substantive disagreement (not a nitpick)
- They must not start with praise ("This is a good answer...")
- They must identify something wrong, oversimplified, or missing
- They must argue for an alternative when the proposal recommends approach X

Challengers are selected to maximize diversity -- models from different providers are preferred over same-model self-critique. Challenges run in parallel for speed.

```
PROPOSE  -->  CHALLENGE
```

!!! note "Sycophancy detection"
    duh scans the opening ~200 characters of each challenge for praise markers like "great answer", "I largely agree", or "no significant flaws". Sycophantic challenges are flagged and excluded from confidence calculations.

### 3. REVISE

The original proposer receives all challenges and produces an improved answer that:

1. Addresses each valid challenge directly
2. Maintains correct points with stronger justification
3. Incorporates new perspectives where they improve the answer
4. Pushes back on wrong challenges with explanations

The revision prompt instructs the model not to mention the debate process -- just give the best possible answer.

```
CHALLENGE  -->  REVISE
```

### 4. COMMIT

A pure extraction step (no model call):

- **Decision** = the revision text
- **Confidence** = computed from challenge quality (0.5 to 1.0). More genuine (non-sycophantic) challenges = higher confidence, because the revision was more rigorously tested.
- **Dissent** = preserved text from genuine challenges, representing minority viewpoints that may be valuable even after revision

```
REVISE  -->  COMMIT
```

## Convergence detection

After COMMIT, duh compares the current round's challenges against the previous round's challenges using **Jaccard word-overlap similarity**:

1. For each current challenge, find the maximum similarity to any previous challenge
2. Average these maximum similarities
3. If the average >= 0.7 (configurable threshold), challenges have **converged**

Convergence means challengers are raising the same issues across rounds. Further iteration is unlikely to improve the answer, so duh stops early.

Round 1 never converges (nothing to compare against).

## Multi-round flow

If challenges haven't converged and rounds remain, the state machine cycles back:

```
COMMIT  -->  PROPOSE  (new round, with previous context)
```

The next round's proposer receives the previous decision and its challenges, so it can build on what was already debated.

When rounds are exhausted or convergence is detected:

```
COMMIT  -->  COMPLETE
```

## State machine

```
IDLE --> PROPOSE --> CHALLENGE --> REVISE --> COMMIT --> COMPLETE
                                               |
                                               +--> PROPOSE (next round)
                                               |
                                               +--> FAILED (on error)
```

Any non-terminal state can transition to FAILED on errors. COMPLETE and FAILED are terminal states.

Guard conditions enforce valid transitions:

- Can't PROPOSE without a non-empty question
- Can't CHALLENGE without a proposal
- Can't REVISE without challenges
- Can't COMMIT without a revision
- Can't start a new round if already converged or max rounds reached
- Can't COMPLETE if not converged and rounds remain

## Next steps

- [Providers and Models](providers-and-models.md) -- How models are selected
- [Cost Management](cost-management.md) -- Token tracking and limits
