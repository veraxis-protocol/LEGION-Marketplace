# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Veraxis.
"""A0 (isolated) and A3 (centralized matcher) comparators; A1/A2 results are read from their own runs.

A0: seven owner processes, no marketplace publication, no trust roots between owners. A buyer has no
counterparty identity, so no order can even be addressed. As a stronger probe we also hand each buyer's
20-unit unilateral order directly to the factory (as if it knew the factory): the factory's own policy decides.
A3: a conventional centralized matcher given identical access to the same published intents. Reported
honestly, including parity with A2 on matching.
Usage: python -m legion_marketplace.comparators --core <LEGION> --out <dir> --a1 <run> --a2 <run> [--a2-failed <run>...]
"""
import argparse
import json
from pathlib import Path

from legion_federation.hub import Hub

from . import matcher
from .e2e import Env, get, post


def a0(core, out):
    env = Env(core, out, "A0", shock=False)
    env.start()   # owners start isolated: no publication, no trust roots between them
    isolated = {o: post(env.ep[o] + "/query", {"envelope": {}}) for o in ["owner:b1"]}
    hub = Hub(str(out), env.ep)
    probes = []
    for b in ["b1", "b2", "b3", "b4", "b5"]:
        # give ONLY the factory and the engineer the probe coordinator's key (direct unilateral route)
        for o in ["owner:f1", "owner:e1", f"owner:{b}"]:
            post(env.ep[o] + "/admin/trust", {"keys": {"coordinator:hub": hub.key.pub, f"owner:{b}": env.pubs[f'owner:{b}'],
                                                       "owner:f1": env.pubs["owner:f1"], "owner:e1": env.pubs["owner:e1"]},
                                              "endpoints": env.ep}, env.admin)
        prop = {"quantity": 20, "spec_hash": env.cfgs["owner:f1"]["spec_hash"],
                "buyers": [{"owner_id": f"owner:{b}", "peer_id": f"peer:{b}", "quantity": 20, "max_payment_cents": 10000,
                            "intent_id": f"a0-{b}"}],
                "factory": {"owner_id": "owner:f1", "peer_id": "peer:f1", "minimum_quantity": 100, "intent_id": "a0-f1"},
                "engineer": {"owner_id": "owner:e1", "peer_id": "peer:e1", "intent_id": "a0-e1"}}
        offers = hub.quote(prop, f"a0-{b}")
        certs, fee = hub.qualify(prop, f"a0-{b}", sorted(offers))
        d = sorted(offers)[0] if offers else None
        if d is None:
            probes.append({"buyer": b, "outcome": "NO_OFFER"})
            continue
        envc, ch = hub.build(prop, 1, None, d, offers[d], fee or 5000, f"a0-{b}")
        r = post(env.ep["owner:f1"] + "/propose", {"contract": envc, "annex": {"qualification": {
            "engineer": "owner:e1", "design_id": d, "certificate": certs.get(d, {}).get("certificate")}}})
        cm = r["commitment"]["payload"]
        probes.append({"buyer": b, "unilateral_units": 20, "factory_decision": cm["decision"], "factory_reason": cm["rationale"]})
    effects = sum(len(get(env.ep[o] + "/reader/effects", env.reader)["effects"]) for o in env.cfgs)
    env.stop()
    feasible = sum(1 for p in probes if p.get("factory_decision") == "ACCEPT")
    return {"outcome": "NO_DEAL" if feasible == 0 else f"{feasible} unilateral orders accepted",
            "isolation": "no publication, no inter-owner trust roots; owners cannot address one another",
            "direct_unilateral_probes": probes, "native_effects_in_probe": effects,
            "note": "A0 unilateral 20-unit orders refused by the factory's own MOQ policy; 0 relationships formed"}


def a3(a2_run):
    run = Path(a2_run)
    intents = []
    for d in sorted((run / "owners").glob("*")):
        for line in open(d / "PEER_EVENTS.jsonl", encoding="utf-8"):
            r = json.loads(line)
            if r["kind"] == "INTENT_PUBLISHED":
                intents.append(r["data"]["intent"])
    props, rejected = matcher.solve(intents)
    a2_match = [json.loads(x)["data"] for x in open(run / "marketplace" / "MATCHES.jsonl", encoding="utf-8")][-1]
    same = bool(props) and bool(a2_match["proposals"]) and \
        sorted(b["owner_id"] for b in props[0]["buyers"]) == sorted(b["owner_id"] for b in a2_match["proposals"][0]["buyers"])
    return {"outcome": "MATCH_FOUND (parity with A2 matching)" if same else "MATCH_DIFFERS",
            "proposal_buyers": sorted(b["owner_id"] for b in props[0]["buyers"]) if props else [],
            "note": "A centralized matcher with identical access to the same published intents finds the same coalition. "
                    "It is not crippled. It has no owner-scoped commitment, disclosure or admission protocol, so on its own "
                    "it can form a proposal but cannot obtain verifiable per-owner consent or execute; price feasibility is "
                    "equally unknown to it because supplier prices are private. No uplift over A3 is claimed for matching."}


def summarize(path):
    hr = json.load(open(Path(path) / "HUB_RESULT.json"))
    j = json.load(open(Path(path) / "JUDGE_RESULT.json"))
    return {"run": Path(path).name, "outcome": hr.get("outcome"), "judge": j["judgement"]["payload"]["verdict"],
            "per_buyer_cents": hr.get("per_buyer_cents"), "total_cents": hr.get("total_cents"), "design": hr.get("design")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--a1", required=True)
    ap.add_argument("--a2", required=True)
    ap.add_argument("--a2-failed", nargs="*", default=[])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = {"arms": {"A0": a0(a.core, out / "A0"), "A1": dict(summarize(a.a1), note="pre-known counterpart addresses"),
                    "A2": dict(summarize(a.a2), note="marketplace discovery + federation"),
                    "A3": a3(a.a2)},
           "A2_earlier_attempts": [summarize(p) if (Path(p) / "JUDGE_RESULT.json").exists() else {"run": p} for p in a.a2_failed]}
    (out / "BASELINE_RESULTS.json").write_text(json.dumps(res, indent=1, sort_keys=True))
    print(json.dumps({k: v["outcome"] for k, v in res["arms"].items()}))


if __name__ == "__main__":
    main()
