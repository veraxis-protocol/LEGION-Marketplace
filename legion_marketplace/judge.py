# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Veraxis. Independently authored.
"""Independent read-only Judge for the seven-collective mission (separate OS process).

Reads: each owner's world state and effect ledger through its reader endpoint (read-only token), each
owner's own hash-chained journals, the coordinator's journals, the marketplace's journals and the
frozen RUN_MANIFEST. It never writes to any owner and never trusts a self-reported DONE.
Usage: python -m legion_marketplace.judge --run <run dir> --manifest RUN_MANIFEST.json [--tamper <mutation>]
"""
import argparse
import copy
import json
import os
import time
import urllib.request
from pathlib import Path

from legion_federation import crypto, schemas
from legion_federation.canonical import new_id, sha256_hex, file_sha256
from legion_federation.journal import verify_chain

PRIVATE_MARKERS = ["CUST-b1-1", "CUST-b2-1", "CUST-b3-1", "CUST-b4-1", "CUST-b5-1", "F-CUST-88", "E-CUST-3", "ACME-PCB",
                   "Delta-Sensors", "pilot deployment budget", "postpone pilot", "fixture QF-7 cost", "price_floor_cents",
                   "margin_floor_cents", "unit_cost_cents"]


def jl(p):
    p = Path(p)
    return [json.loads(x) for x in open(p, encoding="utf-8")] if p.exists() else []


def get(url, token):
    req = urllib.request.Request(url, headers={"X-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def evaluate(run, manifest, token, tamper=None):
    run = Path(run)
    checks = []

    def add(name, ok, **kw):
        checks.append(dict({"check": name, "pass": bool(ok)}, **kw))

    trust = json.load(open(run / "TRUST_ROOTS.json"))["keys"]
    keys = {crypto.key_id(p): p for p in trust.values()}
    owner_of = {crypto.key_id(p): o for o, p in trust.items()}
    ep = json.load(open(run / "endpoints.json"))
    hub_res = json.load(open(run / "HUB_RESULT.json")) if (run / "HUB_RESULT.json").exists() else {}
    final_hash = hub_res.get("contract_hash")
    add("J0_hub_reported_outcome_is_not_trusted_alone", True, hub_outcome=hub_res.get("outcome"))
    versions = jl(run / "CONTRACT_VERSIONS.jsonl")
    final = next((v["data"]["contract"] for v in versions if v["data"]["contract_hash"] == final_hash), None)
    add("J1_final_contract_version_exists", final is not None, contract_hash=final_hash)
    if final is None:
        return finish(checks, run, manifest, None)
    if tamper == "contract_amount":
        final = copy.deepcopy(final)
        final["payments"][0]["amount_cents"] += 100
    add("J1_final_contract_hash_recomputes", sha256_hex(final) == final_hash)
    design = final["design_id"]
    states, effects = {}, {}
    for o, url in ep.items():
        states[o] = get(url + "/reader/state", token)
        effects[o] = get(url + "/reader/effects", token)["effects"]
    if tamper == "missing_buyer":
        states["owner:b3"]["state"]["units"]["received"] = 0
    # --- original obligations of all seven owners, from independent world readback
    for b in [p for p in final["parties"] if p["role"] == "buyer"]:
        o = b["owner_id"]
        st = states[o]["state"]
        line = sum(p["amount_cents"] for p in final["payments"] if p["payer"] == o)
        cap = manifest["e2e"]["owners"][o]["max_payment_cents"]
        need = manifest["e2e"]["owners"][o]["need_units"]
        add("J2_buyer_received_original_quantity", st["units"]["received"] == need and st["units"]["design"] == design,
            owner=o, received=st["units"]["received"], design=st["units"]["design"])
        add("J2_buyer_paid_exact_line_within_cap", st["ledger"]["paid_cents"] == line <= cap, owner=o,
            paid=st["ledger"]["paid_cents"], line=line, cap=cap)
    f = states["owner:f1"]["state"]
    add("J2_factory_produced_contract_quantity", f["produced"][design] == final["quantity"] >= manifest["e2e"]["owners"]["owner:f1"]["moq_units"],
        produced=f["produced"])
    add("J2_factory_shipped_each_buyer", all(f["shipped"][b] == 20 for b in ["b1", "b2", "b3", "b4", "b5"]), shipped=f["shipped"])
    e = states["owner:e1"]["state"]
    add("J2_engineer_qualified_design_by_fixture_readback", e["results"][design]["ran"] and e["results"][design]["pass"],
        results=e["results"])
    add("J2_engineer_certified_lot", e["lots"].get(design) == final["quantity"], lots=e["lots"])
    add("J2_no_unqualified_design_produced", all(v == 0 for d, v in f["produced"].items() if not e["results"][d]["pass"]),
        produced=f["produced"])
    # --- commitments: seven separate owner signatures on the same final version
    commits = [r["data"]["commitment"] for r in jl(run / "OWNER_COMMITMENTS.jsonl")
               if r["data"]["contract_hash"] == final_hash and r["data"].get("commitment")]
    signed = {}
    for env in commits:
        try:
            p = crypto.verify(env, crypto.DOMAINS["commitment"], trusted=keys)
            if owner_of[env["signer"]["key_id"]] == p["owner_id"] and p["decision"] == "ACCEPT" and p["contract_version_hash"] == final_hash:
                signed[p["owner_id"]] = p
        except crypto.VerifyError:
            pass
    parties = {p["owner_id"] for p in final["parties"]}
    add("J3_all_owners_committed_same_final_version", set(signed) == parties == set(manifest["e2e"]["owners"]),
        committed=sorted(signed))
    add("J3_commitments_reference_model_decisions", all(p.get("model_decision_ref") for p in signed.values()))
    # --- authorization by each owner's own admission
    for o in parties:
        pol = jl(run / "owners" / o.split(":")[1] / "POLICY_DECISIONS.jsonl")
        auth = [r for r in pol if r["data"].get("act") == "authorize" and r["data"].get("contract_hash") == final_hash]
        add("J4_owner_authorized_final_version", any(r["data"]["verdict"] == "T" for r in auth), owner=o)
    # --- execution receipts bind to independent effect readbacks
    exe = jl(run / "RECEIPTS.jsonl")
    for r in exe:
        resp = r["data"]["response"]
        for k in ("receipt", "ship_receipt", "buyer_receipt"):
            rc = resp.get(k)
            if not rc:
                continue
            if tamper == "forged_receipt" and k == "receipt":
                rc = copy.deepcopy(rc)
                rc["payload"]["effect_id"] = "eff-000000000000"
            try:
                p = crypto.verify(rc, crypto.DOMAINS["receipt"], trusted=keys)
                issuer = owner_of[rc["signer"]["key_id"]]
                led = {x["effect_id"]: x for x in effects[issuer]}
                x = led.get(p["effect_id"])
                ok = x is not None and p["contract_version_hash"] == final_hash and p["readback_sha256"] == sha256_hex(
                    {kk: x[kk] for kk in ("effect_id", "command_id", "tool", "target", "args")})
            except (crypto.VerifyError, KeyError):
                ok = False
            add("J5_receipt_bound_to_owner_readback", ok, step=r["data"]["action"], kind=k)
    # --- exactly-once and no forbidden effects
    for o, effs in effects.items():
        keys_ = [f"{x['tool']}|{x['target']}" for x in effs]
        add("J6_no_double_effect", len(keys_) == len(set(keys_)), owner=o, effects=keys_)
    if tamper == "duplicate_effect":
        effects["owner:f1"].append(dict(effects["owner:f1"][0]))
        keys_ = [f"{x['tool']}|{x['target']}" for x in effects["owner:f1"]]
        add("J6_no_double_effect", len(keys_) == len(set(keys_)), owner="owner:f1", tampered=True)
    total_paid = sum(states[o]["state"]["ledger"]["paid_cents"] for o in parties if o.startswith("owner:b"))
    add("J7_total_paid_equals_contract_total", total_paid == final["price_basis"]["total_cents"],
        total_paid=total_paid, total=final["price_basis"]["total_cents"])
    add("J7_combined_cap_respected", total_paid <= 50000, total_paid=total_paid)
    # --- disclosure: zero private releases anywhere
    leaks = []
    for o in parties:
        for r in jl(run / "owners" / o.split(":")[1] / "DISCLOSURE_DECISIONS.jsonl"):
            if r["data"].get("private_class") and r["data"].get("verdict") == "T":
                leaks.append((o, r["data"]["field"]))
    add("J8_no_private_field_released", not leaks, leaks=leaks)
    outside = ""
    for name in ["NEGOTIATION_TRACE.jsonl", "CONTRACT_VERSIONS.jsonl", "OWNER_COMMITMENTS.jsonl", "RECEIPTS.jsonl",
                 "ACTION_PERMITS.jsonl", "FULL_TRACE.jsonl"]:
        if (run / name).exists():
            outside += (run / name).read_text(encoding="utf-8")
    for p in (run / "marketplace").glob("*.jsonl"):
        outside += p.read_text(encoding="utf-8")
    hits = [m for m in PRIVATE_MARKERS if m in outside]
    add("J8_no_private_value_outside_owner_processes", not hits, hits=hits)
    # --- shock and same-episode recovery
    trace = jl(run / "NEGOTIATION_TRACE.jsonl")
    full = jl(run / "FULL_TRACE.jsonl")
    shock = [x for x in full if x["kind"] == "PRICE_SHOCK_INJECTED"]
    failed_after = [x for x in trace if x["kind"] == "CONTRACT_STATE" and x["data"]["state"] == "FAILED"
                    and shock and x["t"] >= shock[0]["t"]]
    add("J9_price_shock_injected_once", len(shock) == 1)
    add("J9_prior_terms_invalidated_after_shock", bool(failed_after))
    final_ver = next(v for v in versions if v["data"]["contract_hash"] == final_hash)
    add("J9_recovery_version_created_after_shock", bool(shock) and final_ver["t"] > shock[0]["t"])
    add("J9_single_first_attempt", sum(1 for x in full if x["kind"] == "PROCESS_STARTED" and x["name"] == "coordinator:hub") == 1)
    # --- genuine model-driven decisions per owner
    per_owner = {}
    for o in parties:
        md = jl(run / "owners" / o.split(":")[1] / "MODEL_DECISIONS.jsonl")
        per_owner[o] = sum(1 for r in md if r["data"].get("response_id") and not r["data"].get("failed"))
    hub_md = sum(1 for r in jl(run / "MODEL_DECISIONS.jsonl") if r["data"].get("response_id") and not r["data"].get("failed"))
    add("J10_each_owner_model_active", all(v >= 1 for v in per_owner.values()), per_owner=per_owner, coordinator=hub_md)
    registered = sum(states[o]["workers"]["registered"] for o in parties)
    add("J10_registered_workers", registered == 700, registered=registered)
    # --- journals intact
    bad = []
    for p in list(run.glob("*.jsonl")) + list((run / "owners").glob("*/*.jsonl")) + list((run / "marketplace").glob("*.jsonl")):
        if p.name == "FULL_TRACE.jsonl":
            continue
        ok, n = verify_chain(p)
        if not ok:
            bad.append(str(p.relative_to(run)))
    add("J11_all_hash_chains_valid", not bad, broken=bad)
    # --- A0 counterfactual from the independent oracle (A2 only)
    m = jl(run / "marketplace" / "MATCHES.jsonl")
    if m:
        orc = m[-1]["data"]["oracle"]
        add("J12_A0_no_unilateral_feasible_order", orc["A0_any_feasible"] is False and orc["coalition_exists"] is True,
            a0=orc["A0_unilateral"])
    return finish(checks, run, manifest, {"per_owner_model_decisions": per_owner, "coordinator_model_decisions": hub_md,
                                          "registered_workers": registered, "final_contract_hash": final_hash,
                                          "design": design, "per_buyer_cents": final["price_basis"]["per_buyer_cents"],
                                          "total_cents": final["price_basis"]["total_cents"]})


def finish(checks, run, manifest, facts):
    verdict = "PASS_COMPLETED" if checks and all(c["pass"] for c in checks) else "FAIL"
    return {"verdict": verdict, "checks": checks, "facts": facts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()
    token = os.environ["LMF_READER_TOKEN"]
    manifest = json.load(open(a.manifest))
    res = evaluate(a.run, manifest, token)
    mutants = {}
    for t in ["forged_receipt", "missing_buyer", "duplicate_effect", "contract_amount"]:
        mutants[t] = evaluate(a.run, manifest, token, tamper=t)["verdict"]
    key = crypto.KeyPair()
    run = Path(a.run)
    ev = {p.name: file_sha256(p) for p in sorted(run.glob("*.jsonl"))}
    j = {"schema": "lmf.judgement.v1", "judgement_id": new_id("judge"), "mission_id": manifest["e2e"]["mission_family"],
         "verdict": res["verdict"], "checks": res["checks"], "evidence_sha256": ev,
         "judge_process": {"pid": os.getpid(), "read_only": True, "key_id": key.key_id}, "issued_at": time.time()}
    schemas.validate("Judgement", j)
    out = {"judgement": key.sign(crypto.DOMAINS["judgement"], j), "facts": res["facts"],
           "tamper_mutants": {k: {"verdict": v, "detected": v != "PASS_COMPLETED"} for k, v in mutants.items()}}
    (run / "JUDGE_RESULT.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print(json.dumps({"verdict": res["verdict"], "failed": [c for c in res["checks"] if not c["pass"]][:10],
                      "mutants": out["tamper_mutants"], "facts": res["facts"]}))


if __name__ == "__main__":
    main()
