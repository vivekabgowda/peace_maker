# 00 — Overview & Guiding Principles

## 1. Vision

Build the **Bloomberg Terminal for retail traders in India**: a single, coherent
platform where market data, AI research, scanning, backtesting, portfolio
analytics, journaling, news intelligence, and risk management live together and
reinforce one another — rather than a bag of disconnected features.

BKN AI Capital continuously watches the market during trading hours, ranks
opportunities, explains *why*, and notifies the user only when a high-quality
setup meets predefined criteria.

## 2. Scope

### In scope for the platform (all phases)
- Intraday equities
- Swing trading
- Nifty & Bank Nifty options
- Futures (later phase)
- Long-term portfolio tracking
- Real-time dashboard, scanner, journal, backtester, analytics, news intelligence

### Explicitly out of scope for Version 1
- **Automated / algorithmic order execution.** V1 is advisory only.
- Broker order routing (may arrive in a later, opt-in, heavily-gated phase).
- Providing personalized investment advice in any regulated sense.

## 3. Guiding Principles

### 3.1 Product principles
1. **Transparency over black boxes.** Every recommendation ships with its
   reasoning, the market context, the technical basis, the risks, and the
   conditions that would invalidate it.
2. **Decision support, not decision replacement.** The human is always in the
   loop. The platform ranks and explains; the user decides.
3. **Signal quality over signal quantity.** Notify only on high-conviction,
   criteria-passing setups. Silence is a feature.
4. **One coherent system.** Every module speaks the same domain language and
   shares the same data model.

### 3.2 Risk principles (hard rules — enforced in code)
1. Never recommend trades that exceed predefined risk limits.
2. Never increase exposure after losses (anti-martingale by default).
3. Never chase trades (entry must respect the setup, not the momentum).
4. Always calculate position size before surfacing a recommendation.
5. Always compute expected risk (max loss in ₹ and % of capital).
6. Always explain uncertainty — confidence scores are honest, not marketing.

> The Risk Management Engine is a **gate**, not a panel. A recommendation that
> fails risk checks is discarded before it ever reaches the user.

### 3.3 Engineering principles
- Enterprise architecture: **SOLID**, **Clean Architecture**, **Dependency
  Injection**.
- **Type safety** end to end (TypeScript on the front, Pydantic + type hints on
  the back).
- Comprehensive **structured logging** and **audit trails** for every
  recommendation.
- **Automated testing** as a first-class citizen (unit, integration, contract,
  backtest-regression).
- **Strict linting** and formatting enforced in CI.
- **CI/CD ready** from day one; every service is independently deployable.
- Modularity: **each module is independently maintainable** with explicit
  interfaces.

## 4. Core Modules (at a glance)

| Module | Responsibility |
|--------|----------------|
| Authentication | Signup/login, JWT issuance, sessions, MFA-ready |
| User Profile | Preferences, risk profile, capital, notification settings |
| Dashboard | Aggregated real-time market + portfolio + recommendation view |
| Market Data Service | Ingests quotes, option chains, OI, index data; normalizes and caches |
| Scanner Engine | Continuous multi-universe scanning, indicator computation |
| Strategy Engine | Deterministic strategy rules producing candidate setups |
| AI Recommendation Engine | Multi-agent analysis → single ranked, explained output |
| Risk Management Engine | Position sizing, risk limits, invalidation, hard gating |
| Portfolio Manager | Holdings, exposure, P&L, allocation tracking |
| Trade Journal | Logs decisions, outcomes, notes; feeds analytics |
| Backtesting Engine | Historical simulation of strategies and recommendations |
| Notification Service | Criteria-based alerts across channels (n8n-driven) |
| Analytics | Performance, attribution, behavioral insights |
| Admin Panel | User management, feature flags, model/agent configuration |

## 5. The AI System (at a glance)

A **panel of specialist agents** each produce a structured, scored opinion; an
orchestrator fuses them into one ranked recommendation.

| Agent | Focus |
|-------|-------|
| Market Intelligence Agent | Regime, breadth, index trend, macro context |
| Scanner Agent | Triage of scanner candidates for full analysis |
| Technical Analysis Agent | Price structure, indicators, patterns |
| Options Analysis Agent | Option chain, OI, IV, greeks, strategy selection |
| Swing Trading Agent | Multi-day setups, sector rotation, holding horizon |
| Intraday Agent | Session structure, VWAP, momentum, liquidity |
| News Agent | Event/news sentiment, catalysts, blackout windows |
| Risk Manager | Sizing, drawdown context, veto authority |
| Portfolio Manager | Correlation, concentration, existing exposure |
| Journal Coach | Behavioral guardrails, tilt detection, learning |

Detailed design in [06-ai-agents.md](06-ai-agents.md).

## 6. Success Criteria for the Design Phase

This documentation set is considered "review-ready" when it delivers all of the
founding brief's requested artifacts:

- [x] Complete software architecture — [01](01-architecture.md)
- [x] Folder structure — [02](02-folder-structure.md)
- [x] Database schema — [03](03-database-schema.md)
- [x] API design — [04](04-api-design.md)
- [x] Service architecture — [05](05-service-architecture.md)
- [x] Development roadmap, milestones, sprint plan — [11](11-roadmap.md)
- [x] UI wireframes & design system — [09](09-frontend-ui.md)
- [x] Deployment design — [10](10-deployment.md)

## 7. Glossary

| Term | Meaning |
|------|---------|
| **Setup** | A candidate opportunity emitted by the Strategy/Scanner engines |
| **Recommendation** | A risk-gated, AI-explained, ranked setup shown to the user |
| **Confidence Score** | 0–100 model conviction, calibrated, honest about uncertainty |
| **Invalidation** | Conditions that render a recommendation void |
| **R** | One unit of risk (distance from entry to stop) |
| **RR** | Risk/reward ratio (reward in R) |
| **Universe** | A scanned set of instruments (Nifty 500, F&O, indices, …) |
