# Sprint 11 — Institutional News Intelligence Agent

> **Advisory-only.** News Intelligence produces *explainable research*, never
> orders. It influences the committee's confidence; it cannot place a trade.

## Objective

A permanent, institutional-grade News Intelligence capability that **collects,
classifies, verifies, scores, and explains** news reaching the CIO — behaving
like a professional equity-research analyst, not a headline reader.

Delivered as a **single reusable service** (`app.modules.news_intelligence`) that
the CIO, Scanner, Journal, Analytics, and every future agent consume through one
standardized contract — no duplicated news logic anywhere.

## Architecture

```mermaid
flowchart LR
    subgraph Providers["Plugin providers (NewsProvider ABC)"]
      NSE[NSE] & BSE[BSE] & RBI[RBI] & SEBI[SEBI] & PR[Press/Financial press] & MACRO[Global macro]
    end
    Providers -->|RawArticle → NewsItem| ENG
    subgraph ENG["News Intelligence Engine (reusable, pure)"]
      REL[Source Reliability Engine] --> CLS[Event Classifier]
      CLS --> SESS[Market-Session Awareness]
      SESS --> VER[Multi-source Verification]
      VER --> SCORE[Reliability + recency + session weighted score]
    end
    ENG -->|NewsAssessment| CIO[CIO / News Agent]
    ENG -->|NewsAssessment| SCAN[Scanner]
    ENG -->|NewsAssessment| JRNL[Journal]
    ENG -->|NewsAssessment| ANL[Analytics]
```

The engine is **pure and deterministic** (inject a clock), so the same code runs
in CIO deliberation, Scanner enrichment, Journal snapshots, and Analytics
back-fills. Everything downstream reads the standardized `NewsAssessment`; nobody
re-processes raw articles.

## The standardized contract — `NewsAssessment`

`engine.assess(symbol, items) -> NewsAssessment` is the one entry point.

| Field | Meaning |
|---|---|
| `news_score` | signed −100..+100 |
| `sentiment` | strong_positive … strong_negative |
| `confidence` | 0..1 (blends reliability + verification + corroboration + magnitude) |
| `source_reliability` | 0..100 aggregate |
| `verification_status` | verified / corroborated / single_source / pending / rejected |
| `impact_horizon` | intraday / swing / medium_term / long_term (the *thesis* duration) |
| `impact_timing` | immediate / next_session / multi_day / long_term (*when* it reacts) |
| `dominant_session` | pre_market / during_market / after_market / weekend / holiday |
| `primary_reasons` | explainable analyst prose |
| `risk_factors` | explicit caveats (pending verification, conflicting headlines, out-of-hours) |
| `events` | every classified `EventAssessment` (type, severity, source, reliability, session, timing) |

`.as_dict()` is JSON-serializable for the API / UI / Journal / Analytics.

## Source Reliability Engine (`reliability.py`)

Every source scores 0-100 and buckets into a tier; **unknown sources are rejected**
(never trusted by default), and social feeds score 0 (insufficient on their own).
Ambiguous matches resolve to the **most trusted** source. Extending trust is
data-only — add a row to `_REGISTRY`.

| Example | Tier | Reliability |
|---|---|---|
| NSE / BSE / SEBI / RBI | 1 | 100 |
| Company filing / results | 1 | 98 |
| Investor presentation | 1 | 95 |
| Economic Times / Business Standard / Reuters | 2 | 88-90 |
| Global macro wire | 3 | 75 |
| Financial blog | untrusted | 60 (never sufficient alone) |
| Social media / unknown | rejected | 0 / — |

## Event Taxonomy (`taxonomy.py`)

26 event types (earnings beat/miss, guidance up/down, dividend, buyback, bonus,
split, rights, acquisition, merger, regulatory action, SEBI order, RBI, CEO/CFO
change, rating up/down, bulk/block deal, promoter buy/sell, govt tender, order
win, litigation, sector, general). Each carries an **explainable prior**
(polarity, severity, holding horizon, whether it is *critical* — needs
verification). The classifier refines polarity from the headline text.

## Market-Session Awareness (`sessions.py`)

Reuses the shared NSE calendar. Each event is tagged with its **publication
session** and an estimated **impact timing** — the same earnings print reacts
`immediate` at 10:30 IST but `next_session` at 18:30. Out-of-hours news is
discounted (`session_weight`) because it is diluted by the time the market reopens.

## Multi-source Verification (`verification.py`)

Critical events (SEBI order, M&A, ratings, earnings) require **≥2 independent
sources** for `VERIFIED`; a lone critical source is marked **`PENDING`** — the
platform never front-runs an unverified rumour. Verification scales the score
(`confidence_multiplier`).

## CIO Integration

The CIO computes `contribution = stance × confidence × role_weight`, with
`NEWS = 0.7` vs `TECHNICAL = 1.4`. Because `NewsAssessment.confidence` already
encodes reliability + verification + session, **trustworthy news carries more
weight automatically — with no CIO change** — while news remains subordinate to
the technical read. This satisfies "influence confidence, don't override."

The News agent (`committee/agents/news.py`) votes on the assessment when present
(rich, cited findings) and falls back to the legacy aggregate score otherwise.

## Plugin-Based Architecture

Providers already implement the `NewsProvider` ABC (`fetch() -> [RawArticle]`).
Adding NSE/BSE/RBI/SEBI/premium sources is a new adapter only — the engine and all
consumers are untouched. Future agents (Fundamental, Macro, Institutional Flow,
Economic Calendar, …) plug into the CIO through the same `Agent` interface and can
consume the same `NewsAssessment`.

## What ships in Phase 1 (this PR)

✅ Reusable engine: taxonomy, reliability engine, classifier, session awareness,
verification, standardized `NewsAssessment`, reliability/recency/session-weighted
scoring, explainable reasons + risk factors · ✅ CIO/committee integration
(confidence-weighted, non-overriding) · ✅ Prometheus metrics · ✅ 35 unit tests ·
✅ this doc + architecture diagram.

## Deferred to Phases 2-3 (tracked, not stubbed)

- **Phase 2 — Live sources & history:** Tier-1 provider adapters (NSE/BSE/RBI/SEBI
  corporate-announcement endpoints), the extended historical news DB (headline,
  ts, ticker, source, sentiment, confidence, event type, horizon, verification —
  for later model training), verification persistence, and Scanner-pipeline
  enrichment.
- **Phase 3 — Learning & UX:** continuous self-calibration (was sentiment right?
  did the impact horizon hold? did price actually move?), Scanner/Journal/Analytics
  UI (news score, headlines, horizon, explanation, reliability; news-at-entry/exit
  and supported/contradicted; performance by sentiment/event type), and monitoring
  dashboards.

No placeholder implementations were shipped; deferred items are genuinely
out-of-scope for this PR, not mocked.
