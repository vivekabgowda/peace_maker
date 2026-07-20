# Diagrams

Architecture diagrams for BKN AI Capital are authored **inline as Mermaid** inside
the numbered design documents so they render directly on GitHub and stay
version-controlled next to the prose they explain.

| Diagram | Location |
|---------|----------|
| High-level topology | [../01-architecture.md](../01-architecture.md#2-high-level-topology) |
| Recommendation pipeline (sequence) | [../01-architecture.md](../01-architecture.md#31-the-recommendation-pipeline-the-heart-of-the-system) |
| Module collaboration | [../05-service-architecture.md](../05-service-architecture.md#3-module-catalog--responsibilities) |
| Pipeline state machine | [../05-service-architecture.md](../05-service-architecture.md#5-the-pipeline-as-a-state-machine) |
| AI agent orchestration | [../06-ai-agents.md](../06-ai-agents.md#2-where-ai-sits-in-the-pipeline) |
| Scanner pipeline | [../07-scanner-engine.md](../07-scanner-engine.md#4-pipeline) |
| Risk gate decision flow | [../08-risk-management.md](../08-risk-management.md#3-the-hard-gate-decision-flow) |
| ER overview | [../03-database-schema.md](../03-database-schema.md#2-entity-relationship-overview) |
| Roadmap Gantt | [../11-roadmap.md](../11-roadmap.md#2-phase-overview) |
| CI/CD flow | [../10-deployment.md](../10-deployment.md#4-cicd-github-actions) |

Exported image assets (e.g. for slide decks) may be added to this folder as
needed; the source of truth remains the inline Mermaid.
