# Architecture Decision Records (ADRs)

This directory holds the project's ADRs — short, immutable records of significant
architectural decisions and their context, consequences, and status.

A summary of the initial decisions lives in
[../01-architecture.md](../01-architecture.md#9-key-architectural-decisions-adr-summary).
Individual ADR files (`NNNN-title.md`) are added here as implementation begins,
following the standard template below.

## Template

```md
# ADR-NNNN: <Title>

- Status: Proposed | Accepted | Superseded by ADR-XXXX
- Date: YYYY-MM-DD
- Deciders: <names/roles>

## Context
What forces are at play? What problem are we solving?

## Decision
What did we decide, and why?

## Consequences
What becomes easier or harder as a result? Trade-offs accepted.

## Alternatives Considered
What else was on the table, and why not?
```

## Initial ADRs (see summary table in 01-architecture.md)

| ADR | Decision |
|-----|----------|
| ADR-001 | Modular monolith first, extract hot services later |
| ADR-002 | TimescaleDB inside Postgres instead of a separate TSDB |
| ADR-003 | Risk Engine is the terminal gate; AI cannot bypass it |
| ADR-004 | Deterministic Strategy Engine produces candidates before LLM agents |
| ADR-005 | No auto-execution in V1; advisory only |
| ADR-006 | Celery + Redis for async workers (provisional) |
