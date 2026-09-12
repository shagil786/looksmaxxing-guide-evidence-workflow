# ADR-001: Offline-first evidence brief workflow

## Context

looksmaxxing.guide needs medically cautious, cited content in a niche where unsupported claims are common. The first implementation must be runnable in a short evaluation without API keys, while leaving a clean seam for live retrieval and model-backed agents later.

## Decision

Use a monolith-first, deterministic DAG with consumer-facing stage contracts:

`Planner → ResearchAdapter → Writer → SafetyAuditor → EditorialValidator`

Research returns allowlisted source chunks with `url`, `domain`, `section`, and `chunk_id` metadata. The writer may cite only the supplied context. Auditors run after writing and can fail the brief independently. Every stage emits a JSONL trace event.

## Alternatives considered

- A live Agents API/vector database path now: rejected for the first slice because it adds credentials, deployment, and nondeterministic replay cost.
- A single free-form prompt: rejected because safety and citation checks need independently testable boundaries.
- Separate services: rejected as premature for the expected evaluation scale.

## Consequences

The replay corpus is small and not a substitute for production research. A future live adapter can add semantic/BM25 hybrid retrieval, cached embeddings, reranking, and fresh publication metadata without changing downstream contracts. Publication should remain behind human approval.
