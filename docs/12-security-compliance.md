# 12 — Security & Compliance

## 1. Posture

BKN AI Capital is, in Version 1, a **decision-support platform**: it analyzes,
ranks, and explains — it **does not execute trades** and **does not provide
personalized investment advice** in any regulated sense. This scoping is a
deliberate risk-reduction choice and shapes the security and compliance design.

## 2. Authentication & Authorization

| Aspect | Design |
|--------|--------|
| Auth | JWT: short-lived **access** token (~15 min) + rotating **refresh** token |
| Refresh storage | httpOnly, Secure, SameSite cookie (web); server stores only a hash |
| Password storage | Argon2id (or bcrypt) with per-user salt; never plaintext |
| MFA | TOTP-ready from the schema; enforced for admin accounts |
| Authorization | RBAC (`user`, `admin`); server-side checks on every endpoint |
| Session revocation | Refresh-token revocation table; logout invalidates immediately |
| WS auth | Short-lived ticket exchanged from an authenticated session |

**Principle:** the client is never trusted. All risk limits, permissions, and
ownership checks are enforced server-side.

## 3. Secrets Management

- No secrets in the repository, images, or logs. `.env.example` documents keys;
  real values are injected via environment / a secret manager per environment.
- Separate credentials per environment (local/staging/prod); least privilege.
- Rotation supported for DB creds, provider/broker keys, and JWT signing keys.
- Automated **secret scanning** in CI blocks accidental commits.

## 4. Data Protection

| Data | Handling |
|------|----------|
| In transit | TLS everywhere (proxy terminates TLS; internal mTLS optional) |
| At rest | Disk/volume encryption; DB-level protection for sensitive columns |
| PII | Minimized; email + profile only. No broker credentials stored in V1 |
| Financial data | Portfolio/journal data is user-scoped and access-controlled |
| Backups | Encrypted; access-controlled; restore drills |
| Retention | Time-series tiered (compress/aggregate/expire); user data per policy |

## 5. Application Security

| Threat | Mitigation |
|--------|-----------|
| Injection | Parameterized queries (SQLAlchemy); no string-built SQL |
| XSS | React escaping; strict CSP; sanitize any rendered external text (news) |
| CSRF | SameSite cookies + token checks on state-changing requests |
| SSRF | Allowlist outbound hosts (provider/LLM/news); no user-controlled fetch |
| Rate abuse | Redis token-bucket limits per user & per endpoint |
| Dependency risk | Automated dependency + image scanning in CI; no criticals ship |
| **Prompt injection** | News/external text is treated as **data**, sandboxed, defensively summarized; agents never execute instructions embedded in fetched content ([06](06-ai-agents.md) §8) |
| Enumeration | Generic auth errors; lockout/backoff on repeated failures |

## 6. Auditing & Traceability

- **Immutable audit log** (`audit_log`) for significant actions (auth events,
  risk-limit changes, admin actions, agent-config changes).
- **Every recommendation and every risk decision is persisted** with full context
  and a correlation ID — the platform can always answer "why was this shown / why
  was this rejected?"
- Correlation IDs thread request → pipeline → recommendation across logs and
  traces.

## 7. Regulatory & Ethical Guardrails (India context)

> This section states design intent, not legal advice. Qualified legal counsel
> must review before any public launch, and **before** any future broker-connect
> or execution feature.

- **Advisory scope only (V1):** the product ranks and explains setups; it does not
  place orders and does not offer tailored investment advice.
- **Clear disclaimers:** the UI communicates that outputs are educational/analytical
  decision-support, not guaranteed outcomes, and that trading carries risk of loss.
- **No performance guarantees:** confidence scores are presented as calibrated
  context, explicitly not predictions of profit.
- **SEBI awareness:** research-analyst / investment-adviser regulations, and any
  algo-trading / broker-integration rules, are reviewed *before* features that
  could trigger them (notably any Phase 8 broker-connect) are built. Such features
  are **opt-in, heavily gated, and legally reviewed** — never default-on.
- **Data source compliance:** market-data usage respects exchange/vendor licensing
  and redistribution terms.
- **Auditability for compliance:** the immutable recommendation + risk audit trail
  supports any future compliance or dispute review.

## 8. Risk-Management-as-Security

The Risk Engine ([08](08-risk-management.md)) is itself a safety control:

- It is a **server-enforced terminal gate**; no client or AI path bypasses it.
- Limit changes are audit-logged.
- A **global kill-switch** (feature flag) can immediately pause all
  recommendations (e.g. abnormal market, data corruption, incident).

## 9. Operational Security

- Least-privilege access to infra and databases; admin actions logged.
- Environment isolation (no shared prod/staging credentials or data).
- Incident runbooks (provider outage, data corruption, security incident) authored
  in Phase 0/1 ([10](10-deployment.md) §9).
- Backup restore + failover drills scheduled.

## 10. Security in the SDLC

| Stage | Control |
|-------|---------|
| Design | Threat-model new modules (esp. anything touching money/limits) |
| Code | Strict typing, linting, review; no secrets; safe defaults |
| CI | Dependency/image/secret scanning; SAST where practical |
| Pre-release | Security review of the branch (as a gate for sensitive changes) |
| Runtime | Monitoring, alerting, audit logging, kill-switch |

## 11. Summary of Hard Guarantees

1. No auto-execution in V1.
2. Risk limits enforced server-side; AI cannot bypass the gate.
3. Every recommendation and rejection is auditable.
4. Secrets never in repo/images/logs; scanned in CI.
5. External/AI content is treated as untrusted data.
6. Legal review precedes any execution/broker feature.
