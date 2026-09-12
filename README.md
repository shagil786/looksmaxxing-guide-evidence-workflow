# looksmaxxing.guide Evidence Brief Workflow

An offline-first adaptation of the Dyla architecture for evidence-led, harm-reduction-oriented content briefs. It runs a fixed DAG:

`topic → planner → allowlisted research → cited writer → safety audit → SEO/editorial validation → Markdown + audit + JSONL trace`

## Run

```bash
python3 looksmaxxing_workflow.py "Does creatine cause hair loss?" --out artifacts
python3 -m pytest -q
python3 evaluate_workflow.py
```

The replay adapter uses medical/editorial fixtures and never needs API keys. Its search boundary is explicit in `ALLOWLIST`; a live search adapter can implement the same `search(questions, trace)` contract and retain the downstream audit gates.

Outputs:

- `brief.md` — cited article brief with FAQs and source links
- `audit.json` — safety findings and SEO/editorial checks
- `trace.jsonl` — one structured event per workflow stage, suitable for replay/evaluation

The writer deliberately uses uncertainty language and escalation guidance. This is a content workflow, not medical advice or a diagnosis engine.

The tests include a seeded medical-overclaim defect to keep the safety gate measurable during future adapter changes.
`evaluate_workflow.py` is the bounded evaluator entry point for an independent agent review.
