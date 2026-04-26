# Assessment Methodology

## Proficiency Levels

| Level | Value | Description |
|-------|-------|-------------|
| NONE | 0 | No knowledge or experience |
| BEGINNER | 1 | Basic awareness, can follow tutorials |
| INTERMEDIATE | 2 | Can work independently on standard tasks |
| ADVANCED | 3 | Deep understanding, handles complex scenarios |
| EXPERT | 4 | Authoritative knowledge, can teach others |

## Conversational Assessment

1. **Opening question** — Contextual, practical question at the required proficiency level.
2. **Response evaluation** — LLM scores technical accuracy, depth, and specificity.
3. **Adaptive follow-up** — If the candidate scores above assessed level, the next question probes one level higher; otherwise stays at required level.
4. **Early exit** — Assessment stops when confidence ≥ 0.75 and at least 2 turns have completed.

### Evasion Detection

Responses containing phrases like "I don't know", "not familiar", or fewer than 5 words are flagged as evasive and automatically rated NONE with high confidence.

## Gap Categorisation

| Category | Condition |
|----------|-----------|
| CRITICAL | Required skill, gap ≥ 2 levels |
| MODERATE | Gap = 1 level, or non-critical skill with larger gap |
| MINOR | Small gap on a preferred skill |
| STRENGTH | Candidate meets or exceeds requirement |

## Match Score

```
score = (Σ weight_i × min(assessed_i / required_i, 1.0)) / Σ weight_i × 100
```

Where `weight_i = 2` for required skills and `weight_i = 1` for preferred skills.

## Adjacent Skills

A skill is **adjacent** when the gap is exactly 1 proficiency level. Adjacent skills are prioritised in the learning plan because they build directly on existing knowledge, offering the fastest return on learning investment.

## Learning Plan Sequencing

1. Adjacent skills first (gap = 1).
2. Distant skills after (gap ≥ 2), with prerequisite steps inserted.
3. Within each group, skills are topologically sorted so prerequisites come before dependents.

## Time Estimates

| Transition | Estimated Hours |
|-----------|----------------|
| NONE → BEGINNER | 20 h |
| BEGINNER → INTERMEDIATE | 40 h |
| INTERMEDIATE → ADVANCED | 80 h |
| ADVANCED → EXPERT | 160 h |

Assumes ~10 hours of focused study per week for timeline calculation.
