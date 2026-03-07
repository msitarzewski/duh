# Epistemic Confidence

duh uses a two-dimensional confidence system that separates the quality of the deliberation process (**rigor**) from the theoretical limits of the question domain (**domain cap**). The final **confidence** score reflects both.

## Key concepts

### Rigor

Rigor measures how well the consensus process challenged the answer. It ranges from 0.5 to 1.0 and is computed during the COMMIT phase based on:

- How substantive the challenges were
- Whether the revision addressed the challenges
- Whether multiple rounds of deliberation improved the answer

A high rigor score means the answer survived meaningful scrutiny. A low rigor score means the challenges were weak or the proposer didn't adequately respond.

### Domain caps

Not all questions can be answered with equal certainty. duh classifies each question's **intent** (via taxonomy) and applies a ceiling:

| Domain | Cap | Rationale |
|--------|-----|-----------|
| Factual | 0.95 | Verifiable facts can be highly certain |
| Technical | 0.90 | Technical analysis has some inherent uncertainty |
| Creative | 0.85 | Creative work is subjective |
| Judgment | 0.80 | Value judgments vary by perspective |
| Strategic | 0.70 | Strategy involves unpredictable futures |
| Default | 0.85 | When classification is uncertain |

### Confidence

The final confidence score is:

```
confidence = min(domain_cap(intent), rigor)
```

This means even a perfect deliberation process can't claim 95% confidence on a strategic question -- the domain cap limits it to 70%.

### Intent classification

During the COMMIT phase, duh classifies the question's intent using a taxonomy. The classification determines which domain cap applies. Examples:

- "What year was Python released?" -- factual (cap: 0.95)
- "Should I use PostgreSQL or MongoDB?" -- technical (cap: 0.90)
- "Write a poem about the ocean" -- creative (cap: 0.85)
- "Is remote work better than office work?" -- judgment (cap: 0.80)
- "Should we expand into the European market?" -- strategic (cap: 0.70)

## Calibration

Calibration measures whether confidence scores are accurate over time. A well-calibrated system means:

- Decisions with 90% confidence should be correct ~90% of the time
- Decisions with 70% confidence should be correct ~70% of the time

### Recording outcomes

To build calibration data, record whether decisions were correct:

**CLI**:
```bash
duh feedback <thread-id> success    # Decision was correct
duh feedback <thread-id> failure    # Decision was wrong
duh feedback <thread-id> partial    # Decision was partially correct
```

**Web UI**: Use the inline Pass/Partial/Fail buttons on the Threads page (/threads).

**API**:
```bash
curl -X POST http://localhost:8080/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "abc123", "result": "success"}'
```

### ECE (Expected Calibration Error)

The calibration page shows ECE -- a single number that summarizes how well-calibrated the system is. Lower is better:

- **ECE < 0.05**: Excellent calibration
- **ECE 0.05--0.10**: Good calibration
- **ECE > 0.10**: Needs more data or model adjustment

ECE is computed by:
1. Bucketing decisions by confidence (e.g., 0.7--0.8)
2. Comparing mean predicted confidence to actual success rate in each bucket
3. Averaging the absolute difference, weighted by bucket size

### Viewing calibration

- **CLI**: `duh calibration` shows a table of calibration buckets
- **Web UI**: Visit `/calibration` for a visual calibration curve
- **API**: `GET /api/calibration` returns bucket data

## Related

- [How Consensus Works](how-consensus-works.md) -- The deliberation process that produces rigor scores
- [Web UI](../web-ui.md) -- Calibration page and batch feedback
