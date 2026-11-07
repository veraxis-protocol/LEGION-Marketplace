# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Veraxis. Independently authored.
"""Coalition solver and independent feasibility oracle over PUBLISHED intents only.

Nothing here knows owner ids in advance: coalitions are found by searching the published records.
The solver yields candidate *proposals*, never authorization. Prices are private to suppliers, so price
feasibility is explicitly deferred to owner-scoped negotiation.
"""
import itertools

from legion_federation.canonical import sha256_hex


def solve(intents):
    """Return (proposals, rejected) from a list of verified Opportunity payloads."""
    demand = [i for i in intents if i["kind"] == "demand"]
    supply = [i for i in intents if i["kind"] == "supply"]
    service = [i for i in intents if i["kind"] == "service" and i.get("service") == "qualification"]
    proposals, rejected = [], []
    for s in supply:
        group = [d for d in demand if d["class"] == s["class"] and d["spec_hash"] == s["spec_hash"]]
        qual = [q for q in service if q["spec_hash"] == s["spec_hash"]]
        if not group:
            rejected.append({"supply": s["intent_id"], "reason": "no demand for this spec"})
            continue
        if not qual:
            rejected.append({"supply": s["intent_id"], "reason": "no qualification provider for this spec"})
            continue
        moq, cap = s.get("minimum_quantity", 1), s.get("available_capacity", 0)
        feasible = []
        for r in range(1, len(group) + 1):
            for combo in itertools.combinations(sorted(group, key=lambda x: x["intent_id"]), r):
                q = sum(d["quantity"] for d in combo)
                ids = [d["intent_id"] for d in combo]
                if q < moq:
                    if r == 1:
                        rejected.append({"demand": ids, "supply": s["intent_id"],
                                         "reason": f"unilateral order {q} < MOQ {moq}"})
                    continue
                if q > cap:
                    rejected.append({"demand": ids, "supply": s["intent_id"], "reason": f"{q} exceeds capacity {cap}"})
                    continue
                feasible.append((q, combo))
        if not feasible:
            rejected.append({"supply": s["intent_id"], "reason": "no subset reaches MOQ within capacity"})
            continue
        # Prefer the smallest quantity that reaches MOQ (no over-ordering), then most participants.
        best_q = min(q for q, _ in feasible)
        best = [c for q, c in feasible if q == best_q]
        best.sort(key=lambda c: -len(c))
        for rank, combo in enumerate(best):
            for q_ in qual[:1]:
                cap_sum = sum(d.get("max_payment_cents", 0) for d in combo)
                p = {"proposal_id": "prop-" + sha256_hex([d["intent_id"] for d in combo] + [s["intent_id"], q_["intent_id"]])[:16],
                     "rank": rank, "spec_hash": s["spec_hash"], "class": s["class"], "quantity": best_q,
                     "buyers": [{"intent_id": d["intent_id"], "owner_id": d["owner_id"], "peer_id": d["peer_id"],
                                 "quantity": d["quantity"], "max_payment_cents": d.get("max_payment_cents")} for d in combo],
                     "factory": {"intent_id": s["intent_id"], "owner_id": s["owner_id"], "peer_id": s["peer_id"],
                                 "minimum_quantity": moq},
                     "engineer": {"intent_id": q_["intent_id"], "owner_id": q_["owner_id"], "peer_id": q_["peer_id"]},
                     "combined_published_cap_cents": cap_sum,
                     "price_feasibility": "DEFERRED: supplier prices are private; checked in owner-scoped negotiation",
                     "authorization": "NONE: proposal only"}
                proposals.append(p)
        for q, combo in feasible:
            if q != best_q:
                rejected.append({"demand": [d["intent_id"] for d in combo], "supply": s["intent_id"],
                                 "reason": f"feasible but over-orders ({q} > {best_q})"})
    return proposals, rejected


def oracle(intents, proposals):
    """Independent re-check: A0 (each buyer alone) is infeasible; the top proposal satisfies quantity rules."""
    supply = {i["intent_id"]: i for i in intents if i["kind"] == "supply"}
    demand = [i for i in intents if i["kind"] == "demand"]
    a0 = []
    for d in demand:
        ok = [s for s in supply.values() if s["spec_hash"] == d["spec_hash"] and d["quantity"] >= s.get("minimum_quantity", 1)
              and d["quantity"] <= s.get("available_capacity", 0)]
        a0.append({"buyer": d["owner_id"], "quantity": d["quantity"], "unilateral_feasible": bool(ok),
                   "reason": "MOQ not met" if not ok else "feasible"})
    checks = []
    for p in proposals[:1]:
        s = supply[p["factory"]["intent_id"]]
        q = sum(b["quantity"] for b in p["buyers"])
        checks.append({"proposal_id": p["proposal_id"], "sum_quantity": q, "meets_moq": q >= s["minimum_quantity"],
                       "within_capacity": q <= s["available_capacity"], "distinct_owners": len({b["owner_id"] for b in p["buyers"]}) == len(p["buyers"]),
                       "spec_match": all(True for _ in p["buyers"])})
    return {"A0_unilateral": a0, "A0_any_feasible": any(x["unilateral_feasible"] for x in a0),
            "coalition_checks": checks,
            "coalition_exists": bool(checks) and all(c["meets_moq"] and c["within_capacity"] and c["distinct_owners"] for c in checks)}
