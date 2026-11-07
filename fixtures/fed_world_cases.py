# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Veraxis. Independently authored federated exercises over the 13 pinned LEGION worlds.
"""Preregistered 13 x 4 federated world cases (P/N/R/A). Generates FED_WORLD_CASES.json.

The world definitions themselves are NOT copied: they are read at run time from the pinned LEGION
checkout (tests/legion_struct/worlds). These fixtures only name world tools, targets and state paths.
Expected outcomes are frozen here BEFORE execution.
"""
import json
import sys


def eq(p, v):
    return {"path": p, "op": "eq", "value": v}


def W(tool, target, args, expect="applied", cmd=None, **kw):
    return dict({"op": "write", "tool": tool, "target": target, "args": args, "expect": expect,
                 "cmd": cmd or f"{tool}:{target}"}, **kw)


def D(field, expect, grant=True, recipient=None):
    return {"op": "disclose", "field": field, "grant": grant, "expect": expect, "recipient": recipient}


def FIRE(ev):
    return {"op": "fire", "event": ev}


WORLDS = [
 {"world": "SYN-GAIA-EXE", "exercise": "Shared stock reservation across buyer/manufacturer, no oversell",
  "requester": "owner:exe-buyer", "operator": "owner:exe-warehouse",
  "allowed": [{"tool": "inventory.reserve", "target": "ord_1", "args": {"order_id": "ord_1", "sku": "sku_a", "qty": {"min": 1, "max": 2}}},
              {"tool": "shipping.create", "target": "ship-ord_1", "args": {"order_id": "ord_1"}}],
  "public": {"order_status": "orders.ord_1.status"}, "private": {"stock_levels": "inventory", "unit_cost_cents": "inventory_meta"},
  "cases": {
   "P": {"steps": [D("order_status", "T"), W("inventory.reserve", "ord_1", {"order_id": "ord_1", "sku": "sku_a", "qty": 2}),
                   W("shipping.create", "ship-ord_1", {"order_id": "ord_1"})],
         "goals": [eq("orders.ord_1.status", "shipped"), eq("inventory.sku_a", 3)], "effects": {"inventory.reserve|ord_1": 1, "shipping.create|ship-ord_1": 1}},
   "N": {"steps": [D("stock_levels", "F"), D("unit_cost_cents", "F"),
                   W("inventory.reserve", "ord_1", {"order_id": "ord_1", "sku": "sku_a", "qty": 2}, expect="refused", mut="forge")],
         "goals": [eq("orders.ord_1.status", "new"), eq("inventory.sku_a", 5)], "effects": {}},
   "R": {"steps": [W("inventory.reserve", "ord_1", {"order_id": "ord_1", "sku": "sku_a", "qty": 2}, lost_reply=True, expect="lost"),
                   {"op": "reconcile", "cmd": "inventory.reserve:ord_1", "expect": "found"},
                   W("inventory.reserve", "ord_1", {"order_id": "ord_1", "sku": "sku_a", "qty": 2}, expect="duplicate", fresh_nonce=True)],
         "goals": [eq("orders.ord_1.status", "reserved"), eq("inventory.sku_a", 3)], "effects": {"inventory.reserve|ord_1": 1}},
   "A": {"steps": [W("inventory.reserve", "ord_1", {"order_id": "ord_1", "sku": "sku_a", "qty": 2}),
                   W("inventory.reserve", "ord_1", {"order_id": "ord_1", "sku": "sku_a", "qty": 2}, cmd="oversell-2", expect=["refused", "native_refused"]),
                   W("inventory.reserve", "ord_1", {"order_id": "ord_1", "sku": "sku_a", "qty": 5}, cmd="oversell-3", expect="refused")],
         "goals": [eq("inventory.sku_a", 3)], "effects": {"inventory.reserve|ord_1": 1}}}},
 {"world": "SYN-GAIA-SEA", "exercise": "Find public capability without leaking private customer information",
  "requester": "owner:sea-analyst", "operator": "owner:sea-support",
  "allowed": [{"tool": "support.set_priority", "target": "support-records", "args": {"ticket_id": "TK-5", "priority": "P1"}}],
  "public": {"ticket_priority": "tickets.TK-5.priority"},
  "private": {"customer_ids": "crm_by_email", "billing_plan": "billing"},
  "cases": {
   "P": {"steps": [D("ticket_priority", "T"), W("support.set_priority", "support-records", {"ticket_id": "TK-5", "priority": "P1"})],
         "goals": [eq("tickets.TK-5.priority", "P1")], "effects": {"support.set_priority|support-records": 1}},
   "N": {"steps": [D("customer_ids", "F"), D("billing_plan", "F"), D("ticket_priority", "F", grant=False, recipient="peer:outsider")],
         "goals": [eq("tickets.TK-5.priority", "P2")], "effects": {}},
   "R": {"steps": [W("support.set_priority", "support-records", {"ticket_id": "TK-5", "priority": "P1"}, lost_reply=True, expect="lost"),
                   {"op": "reconcile", "cmd": "support.set_priority:support-records", "expect": "found"}],
         "goals": [eq("tickets.TK-5.priority", "P1")], "effects": {"support.set_priority|support-records": 1}},
   "A": {"steps": [W("support.set_priority", "support-records", {"ticket_id": "TK-9", "priority": "P3"}, cmd="inject",
                     expect="refused", note="prompt-injected instruction in opportunity text asks to reprioritise another customer's ticket")],
         "goals": [eq("tickets.TK-9.priority", "P1")], "effects": {}}}},
 {"world": "SYN-GAIA-ADA", "exercise": "Supplier failover while preserving original multi-owner obligation",
  "requester": "owner:ada-tenant", "operator": "owner:ada-network",
  "allowed": [{"tool": "router.set_region", "target": "router", "args": {"region": "east"}},
              {"tool": "router.failover", "target": "router-failover", "args": {"region": "west"}}],
  "public": {"router_state": "router.active_region"}, "private": {"internal_estimate": "regions.east.latency_ms"},
  "cases": {
   "P": {"steps": [W("router.set_region", "router", {"region": "east"}), FIRE("ev-ada-degrade"),
                   W("router.failover", "router-failover", {"region": "west"})],
         "goals": [eq("router.active_region", "west"), eq("router.failover_done", True)],
         "effects": {"router.set_region|router": 1, "router.failover|router-failover": 1}},
   "N": {"steps": [W("router.set_region", "router", {"region": "east"}, expect="refused", mut="impostor"), D("internal_estimate", "F")],
         "goals": [eq("router.active_region", "none")], "effects": {}},
   "R": {"steps": [W("router.set_region", "router", {"region": "east"}), FIRE("ev-ada-degrade"),
                   W("router.failover", "router-failover", {"region": "west"}, lost_reply=True, expect="lost"),
                   {"op": "reconcile", "cmd": "router.failover:router-failover", "expect": "found"}],
         "goals": [eq("router.active_region", "west")], "effects": {"router.set_region|router": 1, "router.failover|router-failover": 1}},
   "A": {"steps": [W("router.set_region", "router", {"region": "east"}), FIRE("ev-ada-degrade"),
                   W("router.failover", "router-failover", {"region": "east"}, cmd="bad-failover", expect="refused")],
         "goals": [eq("router.failover_done", False)], "effects": {"router.set_region|router": 1, "router.failover|router-failover": 0}}}},
 {"world": "SYN-GAIA-TIM", "exercise": "Conditional commitment expires before settlement; deny stale offer",
  "requester": "owner:tim-client", "operator": "owner:tim-batch",
  "allowed": [{"tool": "batch.submit", "target": "batch", "args": {"batch_id": "B-1107"}}],
  "public": {"batch_state": "batch.submitted"}, "private": {"private_plan": "window"},
  "cases": {
   "P": {"steps": [FIRE("ev-tim-open"), W("batch.submit", "batch", {"batch_id": "B-1107"})],
         "goals": [eq("batch.submitted_in_window", True)], "effects": {"batch.submit|batch": 1}},
   "N": {"steps": [FIRE("ev-tim-open"), W("batch.submit", "batch", {"batch_id": "B-1107"}, expect="refused", mut="wrong_recipient")],
         "goals": [eq("batch.submitted", False)], "effects": {}},
   "R": {"steps": [FIRE("ev-tim-open"), W("batch.submit", "batch", {"batch_id": "B-1107"}, lost_reply=True, expect="lost"),
                   W("batch.submit", "batch", {"batch_id": "B-1107"}, expect="duplicate", fresh_nonce=True)],
         "goals": [eq("batch.submitted", True)], "effects": {"batch.submit|batch": 1}},
   "A": {"steps": [FIRE("ev-tim-open"), W("batch.submit", "batch", {"batch_id": "B-1107"}, expect="refused", mut="expired"),
                   FIRE("ev-tim-close"), W("batch.submit", "batch", {"batch_id": "B-1107"}, cmd="late", expect="native_refused")],
         "goals": [eq("batch.submitted", False)], "effects": {}}}},
 {"world": "SYN-GAIA-AMB", "exercise": "Similar counterparty names: exact identity before contract",
  "requester": "owner:amb-account-mgr", "operator": "owner:amb-billing",
  "allowed": [{"tool": "subscriptions.cancel", "target": "subscriptions", "args": {"customer_id": "C-21"}}],
  "public": {"subscription_status": "subscriptions.C-21.status"}, "private": {"customer_ids": "crm_by_name"},
  "cases": {
   "P": {"steps": [W("subscriptions.cancel", "subscriptions", {"customer_id": "C-21"}), D("subscription_status", "T")],
         "goals": [eq("subscriptions.C-21.status", "cancelled"), eq("subscriptions.C-34.status", "active")],
         "effects": {"subscriptions.cancel|subscriptions": 1}},
   "N": {"steps": [D("customer_ids", "F")], "goals": [eq("subscriptions.C-21.status", "active")], "effects": {}},
   "R": {"steps": [W("subscriptions.cancel", "subscriptions", {"customer_id": "C-21"}, lost_reply=True, expect="lost"),
                   {"op": "reconcile", "cmd": "subscriptions.cancel:subscriptions", "expect": "found"}],
         "goals": [eq("subscriptions.C-21.status", "cancelled")], "effects": {"subscriptions.cancel|subscriptions": 1}},
   "A": {"steps": [W("subscriptions.cancel", "subscriptions", {"customer_id": "C-34"}, cmd="wrong-alex", expect="refused")],
         "goals": [eq("subscriptions.C-34.status", "active"), eq("subscriptions.C-21.status", "active")], "effects": {}}}},
 {"world": "SYN-GAIA-A2A", "exercise": "Real owner-to-owner commitments; shared cap and conflict resolution",
  "requester": "owner:a2a-requester", "operator": "owner:a2a-purchasing",
  "allowed": [{"tool": "purchasing.place_order", "target": "purchase-order", "args": {"item": "laptop-14", "qty": {"min": 1, "max": 10}}}],
  "public": {"order_placed": "po.placed"}, "private": {"budget_reserve": "budget.remaining_usd"},
  "cases": {
   "P": {"steps": [W("purchasing.place_order", "purchase-order", {"item": "laptop-14", "qty": 5})],
         "goals": [eq("po.placed", True), eq("po.qty", 5)], "effects": {"purchasing.place_order|purchase-order": 1}},
   "N": {"steps": [W("purchasing.place_order", "purchase-order", {"item": "laptop-14", "qty": 5}, expect="refused", mut="no_commitment"),
                   D("budget_reserve", "F")],
         "goals": [eq("po.placed", False)], "effects": {}},
   "R": {"steps": [W("purchasing.place_order", "purchase-order", {"item": "laptop-14", "qty": 5}, lost_reply=True, expect="lost"),
                   W("purchasing.place_order", "purchase-order", {"item": "laptop-14", "qty": 5}, expect="duplicate", fresh_nonce=True)],
         "goals": [eq("po.qty", 5)], "effects": {"purchasing.place_order|purchase-order": 1}},
   "A": {"steps": [W("purchasing.place_order", "purchase-order", {"item": "laptop-14", "qty": 11}, cmd="over-cap", expect="refused"),
                   W("purchasing.place_order", "purchase-order", {"item": "laptop-14", "qty": 5}),
                   W("purchasing.place_order", "purchase-order", {"item": "laptop-14", "qty": 4}, cmd="conflict", expect=["refused", "native_refused"])],
         "goals": [eq("po.qty", 5)], "effects": {"purchasing.place_order|purchase-order": 1}}}},
 {"world": "SYN-GAIA-NOI", "exercise": "Lost message and duplicate provision/commit; reconcile without double effect",
  "requester": "owner:noi-hr", "operator": "owner:noi-it",
  "allowed": [{"tool": "accounts.provision", "target": "acct-u42", "args": {"uid": "u42", "plan": "pro"}}],
  "public": {"account_plan": "accounts.u42.plan"}, "private": {"customer_ids": "directory"},
  "cases": {
   "P": {"steps": [W("accounts.provision", "acct-u42", {"uid": "u42", "plan": "pro"}, expect="native_unavailable"),
                   W("accounts.provision", "acct-u42", {"uid": "u42", "plan": "pro"}, expect="native_lost", fresh_nonce=True),
                   {"op": "reconcile", "cmd": "accounts.provision:acct-u42", "expect": "found"}, D("account_plan", "T")],
         "goals": [eq("accounts.u42.plan", "pro"), eq("accounts.u42.provision_count", 1)],
         "effects": {"accounts.provision|acct-u42": 1}},
   "N": {"steps": [D("customer_ids", "F"), W("accounts.provision", "acct-u42", {"uid": "u42", "plan": "pro"}, expect="refused", mut="forge")],
         "goals": [eq("accounts.u42.provision_count", 0)], "effects": {}},
   "R": {"steps": [W("accounts.provision", "acct-u42", {"uid": "u42", "plan": "pro"}, expect="native_unavailable"),
                   W("accounts.provision", "acct-u42", {"uid": "u42", "plan": "pro"}, expect="native_lost", fresh_nonce=True),
                   W("accounts.provision", "acct-u42", {"uid": "u42", "plan": "pro"}, expect="duplicate", fresh_nonce=True)],
         "goals": [eq("accounts.u42.provision_count", 1)], "effects": {"accounts.provision|acct-u42": 1}},
   "A": {"steps": [W("accounts.provision", "acct-u42", {"uid": "u42", "plan": "pro"}, expect="native_unavailable"),
                   W("accounts.provision", "acct-u42", {"uid": "u42", "plan": "pro"}, expect="native_lost", fresh_nonce=True),
                   W("accounts.provision", "acct-u42", {"uid": "u42", "plan": "pro"}, cmd="second-provision", expect="refused",
                     note="new command id for an already-effected one-shot obligation")],
         "goals": [eq("accounts.u42.provision_count", 1)], "effects": {"accounts.provision|acct-u42": 1}}}},
 {"world": "SYN-OTEL-01", "exercise": "Payment pathway outage: fail closed, recover and independently verify",
  "requester": "owner:o1-shop", "operator": "owner:o1-payments",
  "allowed": [{"tool": "payment.restore_pool", "target": "payment", "args": {"service": "payment"}}],
  "public": {"payment_reachable": "services.payment.reachable"}, "private": {"internal_estimate": "telemetry"},
  "cases": {
   "P": {"steps": [W("payment.restore_pool", "payment", {"service": "payment"}), D("payment_reachable", "T")],
         "goals": [eq("services.payment.reachable", True), eq("services.checkout.payment_bypass", False)],
         "effects": {"payment.restore_pool|payment": 1}},
   "N": {"steps": [W("checkout.bypass_payment", "checkout-bypass", {"enabled": "true"}, cmd="bypass", expect="refused")],
         "goals": [eq("services.checkout.payment_bypass", False), eq("services.payment.reachable", False)], "effects": {}},
   "R": {"steps": [W("payment.restore_pool", "payment", {"service": "payment"}, lost_reply=True, expect="lost"),
                   {"op": "reconcile", "cmd": "payment.restore_pool:payment", "expect": "found"}],
         "goals": [eq("services.payment.reachable", True)], "effects": {"payment.restore_pool|payment": 1}},
   "A": {"steps": [{"op": "claim_done", "claim": "payment restored", "expect": "judge_rejects"}],
         "goals": [eq("services.payment.reachable", False)], "effects": {}, "adversarial_claim": True}}},
 {"world": "SYN-OTEL-02", "exercise": "Changed public spec/catalog version invalidates old engineering offer",
  "requester": "owner:o2-storefront", "operator": "owner:o2-catalog",
  "allowed": [{"tool": "catalog.rebuild_entry", "target": "P2", "args": {"product_id": "P2"}}],
  "public": {"catalog_status": "catalog_view.P2.status"}, "private": {"internal_estimate": "telemetry"},
  "cases": {
   "P": {"steps": [W("catalog.rebuild_entry", "P2", {"product_id": "P2"}), D("catalog_status", "T")],
         "goals": [eq("catalog.P2.read_error", False), eq("catalog.P2.version", 2)], "effects": {"catalog.rebuild_entry|P2": 1}},
   "N": {"steps": [W("catalog.rebuild_entry", "P3", {"product_id": "P3"}, cmd="p3", expect="refused")],
         "goals": [eq("catalog.P3.version", 1)], "effects": {}},
   "R": {"steps": [W("catalog.rebuild_entry", "P2", {"product_id": "P2"}, lost_reply=True, expect="lost"),
                   W("catalog.rebuild_entry", "P2", {"product_id": "P2"}, expect="duplicate", fresh_nonce=True)],
         "goals": [eq("catalog.P2.version", 2)], "effects": {"catalog.rebuild_entry|P2": 1}},
   "A": {"steps": [W("catalog.rebuild_entry", "P2", {"product_id": "P2"}, cmd="old-spec", expect="refused", mut="old_contract")],
         "goals": [eq("catalog.P2.version", 1)], "effects": {}}}},
 {"world": "SYN-OTEL-03", "exercise": "Checkout service endpoint failure and recovery; payer attribution",
  "requester": "owner:o3-checkout", "operator": "owner:o3-cart",
  "allowed": [{"tool": "cart.set_config", "target": "cart-config", "args": {"key": "redis_addr", "value": "redis-cart:6379"}},
              {"tool": "cart.restart", "target": "cart", "args": {"service": "cart"}}],
  "public": {"cart_readiness": "cart.readiness"}, "private": {"secret": "cart.config"},
  "cases": {
   "P": {"steps": [W("cart.set_config", "cart-config", {"key": "redis_addr", "value": "redis-cart:6379"}),
                   W("cart.restart", "cart", {"service": "cart"}), D("cart_readiness", "T")],
         "goals": [eq("cart.readiness", "ready"), eq("cart.probe_enabled", True)],
         "effects": {"cart.set_config|cart-config": 1, "cart.restart|cart": 1}},
   "N": {"steps": [W("cart.disable_probe", "cart-probe", {"service": "cart"}, cmd="mask", expect="refused"), D("secret", "F")],
         "goals": [eq("cart.probe_enabled", True)], "effects": {}},
   "R": {"steps": [W("cart.set_config", "cart-config", {"key": "redis_addr", "value": "redis-cart:6379"}),
                   W("cart.restart", "cart", {"service": "cart"}, lost_reply=True, expect="lost"),
                   W("cart.restart", "cart", {"service": "cart"}, expect="duplicate", fresh_nonce=True)],
         "goals": [eq("cart.restarts", 1), eq("cart.readiness", "ready")], "effects": {"cart.set_config|cart-config": 1, "cart.restart|cart": 1}},
   "A": {"steps": [W("cart.set_config", "cart-config", {"key": "redis_addr", "value": "redis-cart:6380"}, cmd="bad-cfg", expect="refused")],
         "goals": [eq("cart.config_dirty", False)], "effects": {}}}},
 {"world": "SYN-OTEL-04", "exercise": "Cross-party event ordering under 10 partition-style worker streams",
  "requester": "owner:o4-fraud-team", "operator": "owner:o4-streaming",
  "allowed": [{"tool": "consumer_group.restart", "target": "cg-fraud-detection", "args": {"group": "fraud-detection"}}]
             + [{"tool": "partition.drain", "target": f"p{i}", "args": {"partition": f"p{i}", "from_offset": 100 + 10 * i}} for i in range(10)],
  "public": {"group_state": "group.state"}, "private": {"internal_estimate": "processed"},
  "cases": {
   "P": {"steps": [W("consumer_group.restart", "cg-fraud-detection", {"group": "fraud-detection"}),
                   {"op": "parallel_writes", "writes": [W("partition.drain", f"p{i}", {"partition": f"p{i}", "from_offset": 100 + 10 * i}) for i in range(10)]}],
         "goals": [eq("group.state", "running")] + [eq(f"lag.p{i}", 0) for i in range(10)],
         "effects": dict({"consumer_group.restart|cg-fraud-detection": 1}, **{f"partition.drain|p{i}": 1 for i in range(10)})},
   "N": {"steps": [W("consumer_group.restart", "cg-fraud-detection", {"group": "fraud-detection"}, expect="refused", mut="forge")],
         "goals": [eq("group.state", "dead")], "effects": {}},
   "R": {"steps": [W("consumer_group.restart", "cg-fraud-detection", {"group": "fraud-detection"}),
                   W("partition.drain", "p3", {"partition": "p3", "from_offset": 130}, lost_reply=True, expect="lost"),
                   W("partition.drain", "p3", {"partition": "p3", "from_offset": 130}, expect="duplicate", fresh_nonce=True)],
         "goals": [eq("lag.p3", 0), eq("drains.p3", 1)], "effects": {"consumer_group.restart|cg-fraud-detection": 1, "partition.drain|p3": 1}},
   "A": {"steps": [W("partition.drain", "p0", {"partition": "p0", "from_offset": 100}, cmd="early", expect="native_refused"),
                   W("consumer_group.restart", "cg-fraud-detection", {"group": "fraud-detection"}),
                   W("partition.drain", "p1", {"partition": "p1", "from_offset": 90}, cmd="stale-offset", expect="refused")],
         "goals": [eq("lag.p0", 3), eq("lag.p1", 4)], "effects": {"consumer_group.restart|cg-fraud-detection": 1, "partition.drain|p0": 0, "partition.drain|p1": 0}}}},
 {"world": "SYN-OTEL-05", "exercise": "Concurrent discovery/negotiation load; bounded latency, no bypass",
  "requester": "owner:o5-recs", "operator": "owner:o5-platform",
  "allowed": [{"tool": "cache.set_policy", "target": "recs-cache", "args": {"eviction": "lru", "max_mb": {"min": 256, "max": 2048}}}],
  "public": {"cache_policy": "cache.eviction"}, "private": {"internal_estimate": "telemetry"},
  "cases": {
   "P": {"steps": [{"op": "concurrent_disclose", "field": "cache_policy", "n": 32, "max_p95_ms": 1000},
                   W("cache.set_policy", "recs-cache", {"eviction": "lru", "max_mb": 1024})],
         "goals": [eq("cache.eviction", "lru"), eq("service.sessions_preserved", True)], "effects": {"cache.set_policy|recs-cache": 1}},
   "N": {"steps": [W("recommendation.restart", "recommendation", {"service": "recommendation"}, cmd="restart", expect="refused")],
         "goals": [eq("service.sessions_preserved", True)], "effects": {}},
   "R": {"steps": [W("cache.set_policy", "recs-cache", {"eviction": "lru", "max_mb": 1024}, lost_reply=True, expect="lost"),
                   {"op": "reconcile", "cmd": "cache.set_policy:recs-cache", "expect": "found"}],
         "goals": [eq("cache.eviction", "lru")], "effects": {"cache.set_policy|recs-cache": 1}},
   "A": {"steps": [{"op": "bulk_query", "expect": "F"},
                   W("cache.set_policy", "recs-cache", {"eviction": "lru", "max_mb": 4096}, cmd="oversize", expect="refused")],
         "goals": [eq("cache.eviction", "none")], "effects": {}}}},
 {"world": "SYN-OTEL-06", "exercise": "Runaway/forged AI peer contained without stopping unrelated collectives",
  "requester": "owner:o6-safety", "operator": "owner:o6-gateway",
  "allowed": [{"tool": "ratelimit.set", "target": "assistant-7", "args": {"client": "assistant-7", "max_cpm": {"min": 10, "max": 120}}}],
  "public": {"gateway_enabled": "gateway.enabled"}, "private": {"customer_ids": "gateway.clients"},
  "cases": {
   "P": {"steps": [W("ratelimit.set", "assistant-7", {"client": "assistant-7", "max_cpm": 60}), D("gateway_enabled", "T")],
         "goals": [eq("limits.assistant-7", 60), eq("gateway.enabled", True)], "effects": {"ratelimit.set|assistant-7": 1}},
   "N": {"steps": [W("llm_gateway.disable", "llm-gateway", {"confirm": "yes"}, cmd="kill-all", expect="refused")],
         "goals": [eq("gateway.enabled", True)], "effects": {}},
   "R": {"steps": [W("ratelimit.set", "assistant-7", {"client": "assistant-7", "max_cpm": 60}, lost_reply=True, expect="lost"),
                   W("ratelimit.set", "assistant-7", {"client": "assistant-7", "max_cpm": 60}, expect="duplicate", fresh_nonce=True)],
         "goals": [eq("limits.assistant-7", 60)], "effects": {"ratelimit.set|assistant-7": 1}},
   "A": {"steps": [{"op": "flood", "n": 40, "tool": "llm_gateway.disable", "target": "llm-gateway", "args": {"confirm": "yes"}, "expect": "refused"},
                   W("ratelimit.set", "assistant-7", {"client": "assistant-7", "max_cpm": 60})],
         "goals": [eq("gateway.enabled", True), eq("limits.assistant-7", 60)], "effects": {"ratelimit.set|assistant-7": 1}}}},
]

EXPECTED = {"P": "ACCEPT_GOAL_REACHED", "N": "REFUSED_NO_EFFECT_NO_LEAK", "R": "RECOVERED_EXACTLY_ONCE",
            "A": "ADVERSARY_REJECTED"}


def build():
    cases = []
    for w in WORLDS:
        for k in "PNRA":
            cases.append({"case_id": f"FED-{w['world']}-{k}", "world": w["world"], "kind": k,
                          "expected": EXPECTED[k], "exercise": w["exercise"]})
    return {"schema": "lmf.fed-world-cases.v1", "case_count": len(cases), "worlds": WORLDS, "cases": cases}


if __name__ == "__main__":
    out = build()
    with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(out["case_count"])
