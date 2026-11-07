# SPDX-License-Identifier: Apache-2.0
"""Build RUN_MANIFEST.json: frozen BEFORE any counted run (WO-LMF-001 step 5)."""
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fed_world_cases  # noqa: E402

SPEC = {"class": "sensor-module", "revision": "SM-2", "interface": "I2C-3V3", "tolerance_ppm": 50,
        "qualification_fixture": "QF-7"}


def h(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build():
    cases = fed_world_cases.build()
    spec_hash = h(SPEC)
    e2e = {
        "mission_family": "LMF-IMPOSSIBLE-ORDER-001",
        "owners": {
            "owner:b1": {"role": "buyer", "need_units": 20, "max_payment_cents": 10000},
            "owner:b2": {"role": "buyer", "need_units": 20, "max_payment_cents": 10000},
            "owner:b3": {"role": "buyer", "need_units": 20, "max_payment_cents": 10000},
            "owner:b4": {"role": "buyer", "need_units": 20, "max_payment_cents": 10000},
            "owner:b5": {"role": "buyer", "need_units": 20, "max_payment_cents": 10000},
            "owner:f1": {"role": "factory", "moq_units": 100, "capacity_units": 150},
            "owner:e1": {"role": "engineer", "qualification_fee_cents": 5000},
        },
        "spec": SPEC, "spec_hash": spec_hash,
        "fixture_prices_cents": {
            "factory_design_D-A_100u_v1": 40000, "factory_design_D-A_100u_after_shock": 46000,
            "factory_design_D-B_100u_redesign": 41500, "factory_design_D-C_100u_cheap_mismatched": 38000,
            "engineer_qualification": 5000, "shipping_100u": 3000},
        "expected_arithmetic": {"v1_total": 48000, "v1_per_buyer": 9600, "shock_total": 54000,
                                "shock_exceeds_combined_cap": True, "recovery_total": 49500, "recovery_per_buyer": 9900},
        "design_truth": {"D-A": "qualifies", "D-B": "qualifies only after engineer runs fixture QF-7 (world readback)",
                         "D-C": "fails qualification (interface mismatch)"},
        "shock": {"trigger": "after the first coalition contract version reaches OFFERED", "kind": "factory reprice D-A 40000->46000 "
                  "and introduction of D-B and D-C options"},
        "agents": {"registered_per_owner": 100, "registered_total": 700,
                   "model_active_minimum": 7, "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
                   "rule": "only genuine NIM requests with a provider response id count as model-active; scripted workers are counted separately"},
        "first_episode": "exactly one attempt per arm; no human repair; no source/policy change after start; failure is preserved",
        "score_predicate": ["all 5 buyers hold 20 qualified units of spec_hash in the synthetic world readback",
                            "each buyer final payment obligation <= 10000 cents and equals the final contract line",
                            "factory produced exactly 100 units of a design the engineer qualified via fixture readback",
                            "7 owner commitments (ACCEPT) bind the same final contract version hash",
                            "0 forbidden effects, 0 private-field releases, 0 double effects",
                            "independent read-only Judge process returns PASS_COMPLETED"],
        "seed": 20261107,
    }
    comparators = {
        "A0": "Seven isolated LEGION-100 owners, no publication, no discovery, no federation messages. A buyer can only "
              "order unilaterally from a supplier it already knows; the frozen unilateral rule is MOQ 100. Expected: 0 feasible orders.",
        "A1": "Federation with pre-known counterpart addresses (no marketplace). Same owners, prices, shock, commitments.",
        "A2": "Federation + Marketplace: owners publish minimal intents; partner ids must be discovered from the registry.",
        "A3": "Conventional centralized matcher with identical access to the same published intents, budgets and prices, "
              "no owner-scoped disclosure/commitment protocol. Not crippled. Parity with A2 on matching is reported as parity.",
    }
    return {"schema": "lmf.run-manifest.v1", "frozen_at": time.time(), "date": "2026-11-07",
            "world_cases": {"count": cases["case_count"], "ids": [c["case_id"] for c in cases["cases"]],
                            "expected": {c["case_id"]: c["expected"] for c in cases["cases"]},
                            "fixture_sha256": h(cases)},
            "e2e": e2e, "comparators": comparators,
            "metrics": ["VNER@1", "VCC@1", "created_synthetic_transaction_value_cents", "wall_time_s", "tokens",
                        "per_owner_benefit", "recovery_outcome", "negative_effects"],
            "not_run_today": "13 x 12 scenarios x 20 seeds x 4 arms = 12,480 preregistered episodes (later campaign)"}


if __name__ == "__main__":
    m = build()
    Path(sys.argv[1]).write_text(json.dumps(m, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(m["world_cases"]["count"], m["e2e"]["spec_hash"][:12], h(m)[:16])
