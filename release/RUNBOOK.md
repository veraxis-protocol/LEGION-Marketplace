# RUNBOOK — LEGION Market Genesis demonstration

## One command (Windows PowerShell)
```
git clone https://github.com/veraxis-protocol/LEGION-Marketplace.git
cd LEGION-Marketplace
.\run_market_genesis_demo.ps1 -NimKeyFile C:\path\to\nvapi.txt
```
It clones LEGION Core at d083c44 (PolyForm Noncommercial) and LEGION-Federation next to this repo, creates a venv
from `requirements.lock`, runs the schema tests, the 13 x 4 federated world cases with an independent Judge per
world, the seven-owner first attempt with the live dashboard at http://127.0.0.1:8790/, and the adversarial
negative suites. Evidence goes to `..\runs\demo-<timestamp>\`.

## What runs (all separate OS processes)
| Process | Count | Holds |
|---|---|---|
| owner peer (`legion_federation.owner_peer`) | 7 (b1–b5 buyers, f1 factory, e1 engineer) | own Ed25519 key, private profile, LEGION world, journals, 100 registered workers, 1 NIM agent |
| marketplace registry | 1 | published projections only |
| coordinator (`legion_federation.hub`) | 1 | own key, no authority over any owner, NIM planner |
| Judge (`legion_marketplace.judge`) | 1 | read-only token; never writes |

## Labels
SIMULATED: manufacture, qualification, shipping, buyer ledger payments (world-engine effects in each owner's process).
REAL_SANDBOX: PayPal Sandbox payments, made only through LEGION-Commerce with the platform operator's signed authorization
and each buyer's own approval on PayPal (see [LEGION Deal Rescue](https://github.com/veraxis-protocol/LEGION-Deal-Rescue)).
LIVE / REPLAY: dashboard mode while a run writes / after the Judge has finished.

## Not claimed
Physical manufacture or delivery; multi-merchant settlement; Lean proof of federation safety (the Federation-edge
policies are tested, not proved); 700 LLMs (700 are registered; model-active counts are in the Judge facts);
the 12,480-episode campaign (not run).
