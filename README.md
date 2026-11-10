# LEGION-Marketplace

A marketplace of *economic intentions*, not a product catalogue. Owners publish minimal, signed, owner-scoped
intent projections; the matcher discovers coalitions that no single owner could form alone (for example five 20-unit
buyers and a 100-unit-MOQ factory) and hands a *proposal* to LEGION-Federation for negotiation. The marketplace never
spends, never sees owner secrets and never changes anyone's mission.

## What is here
* `legion_marketplace/` – intent registry (HTTP), coalition solver, independent feasibility oracle, baseline comparators (buyers alone, known peers, discovery plus federation, central matcher),
  seven-owner end-to-end mission, read-only Judge, live dashboard.
* `fixtures/` – preregistered 13-world federated case matrix (`FED_WORLD_CASES.json`) and `RUN_MANIFEST.json`.
* `ui/` – dashboard.
* `run_market_genesis_demo.ps1` – one-command local demonstration; `release/` – runbook, demo script, storyboard, and a dated eligibility record.

All prices are synthetic fixture quotes. Manufacturing, qualification and delivery are SIMULATED world effects.
PayPal Sandbox effects, when present, are labelled REAL_SANDBOX and are shown separately.

## Related repositories

| Repository | Role | License |
|---|---|---|
| [LEGION-Deal-Rescue](https://github.com/veraxis-protocol/LEGION-Deal-Rescue) | Merchant application and PayPal AI Hackathon entry built on this stack | Apache-2.0 |
| [LEGION](https://github.com/veraxis-protocol/LEGION) | LEGION Core runtime (100 registered workers per collective, worlds, Judge) | PolyForm Noncommercial 1.0.0 |
| [LEGION-Formal-Core](https://github.com/veraxis-protocol/LEGION-Formal-Core) | Lean 4 model of single-collective admission and completion | PolyForm Noncommercial 1.0.0 |
| [LEGION-Federation](https://github.com/veraxis-protocol/LEGION-Federation) | Owner-isolated peers, disclosure policy, multi-owner contracts | PolyForm Noncommercial 1.0.0 |
| [LEGION-Marketplace](https://github.com/veraxis-protocol/LEGION-Marketplace) | Intent publication, discovery, end-to-end harness, independent Judge | PolyForm Noncommercial 1.0.0 |
| [LEGION-Commerce](https://github.com/veraxis-protocol/LEGION-Commerce) | PayPal Sandbox gateway, admission bridge, payment orchestration | no license file (all rights reserved) |

## License
PolyForm Noncommercial License 1.0.0 (since 2026-11-07). Not an OSI open-source license. See `NOTICE`.
