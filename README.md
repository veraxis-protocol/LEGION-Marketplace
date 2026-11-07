# LEGION-Marketplace

A marketplace of *economic intentions*, not a product catalogue. Owners publish minimal, signed, owner-scoped
intent projections; the matcher discovers coalitions that no single owner could form alone (for example five 20-unit
buyers and a 100-unit-MOQ factory) and hands a *proposal* to LEGION-Federation for negotiation. The marketplace never
spends, never sees owner secrets and never changes anyone's mission.

## What is here
* `legion_marketplace/` – intent registry (HTTP), coalition solver, independent feasibility oracle, A0–A3 comparators,
  seven-owner end-to-end mission, read-only Judge, live dashboard.
* `fixtures/` – preregistered 13-world federated case matrix (`FED_WORLD_CASES.json`) and `RUN_MANIFEST.json`.
* `ui/` – dashboard.

All prices are synthetic fixture quotes. Manufacturing, qualification and delivery are SIMULATED world effects.
PayPal Sandbox effects, when present, are labelled REAL_SANDBOX and are shown separately.

## License
Apache-2.0 for files in this repository only; LEGION Core runtime dependency is PolyForm Noncommercial. See `NOTICE`.
