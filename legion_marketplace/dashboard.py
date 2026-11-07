# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Veraxis.
"""Read-only dashboard over a run directory (LIVE while a run writes, REPLAY afterwards).

python -m legion_marketplace.dashboard --run <run dir> [--port 8790] [--worlds <WO-005 run dir>] [--negatives <dir>]
It only reads evidence files. The optional negative button (LIVE only) sends one unregistered-identity
request for a private factory field and shows the refusal and the unchanged effect ledger.
"""
import argparse
import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from legion_federation import crypto
from legion_federation.canonical import new_id, now

UI = Path(__file__).resolve().parents[1] / "ui" / "index.html"


def jl(p):
    p = Path(p)
    if not p.exists():
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def js(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def snapshot(run, worlds=None, negatives=None, comparators=None):
    run = Path(run)
    owners = {}
    for d in sorted((run / "owners").glob("*")) if (run / "owners").exists() else []:
        cfg = js(run / f"config_{d.name}.json") or {}
        md = jl(d / "MODEL_DECISIONS.jsonl")
        owners[f"owner:{d.name}"] = {
            "role": cfg.get("role"), "pseudonym": cfg.get("pseudonym"), "mission": (cfg.get("mission") or {}).get("statement"),
            "published_fields": cfg.get("discovery_fields"), "registered_workers": 100,
            "model_decisions": [{"task": r["data"]["task"], "decision": r["data"].get("decision"),
                                 "response_id": r["data"].get("response_id"), "model": r["data"].get("model")}
                                for r in md if not r["data"].get("failed")],
            "disclosures": [r["data"] for r in jl(d / "DISCLOSURE_DECISIONS.jsonl")][-12:],
            "admissions": [{"act": r["data"].get("act"), "verdict": r["data"].get("verdict"),
                            "failed": [c["check"] for c in r["data"].get("checks", []) if c["ok"] is not True]}
                           for r in jl(d / "POLICY_DECISIONS.jsonl")],
            "native": [{"tool": r["data"]["tool"], "target": r["data"]["target"], "status": r["data"]["status"],
                        "duplicate": r["data"].get("duplicate")} for r in jl(d / "PEER_EVENTS.jsonl") if r["kind"] == "NATIVE_CALL"]}
    full = jl(run / "FULL_TRACE.jsonl")
    hub_md = jl(run / "MODEL_DECISIONS.jsonl")
    return {
        "mode": "LIVE" if not (run / "JUDGE_RESULT.json").exists() else "REPLAY", "t": time.time(), "run": run.name,
        "owners": owners,
        "marketplace": {"publications": [r["data"] for r in jl(run / "marketplace" / "INTENT_PUBLICATIONS.jsonl")],
                        "matches": [r["data"] for r in jl(run / "marketplace" / "MATCHES.jsonl")][-1:]},
        "negotiation": [{"t": r["t"], "kind": r["kind"], "data": r["data"]} for r in jl(run / "NEGOTIATION_TRACE.jsonl")],
        "versions": [{"version": r["data"]["version"], "hash": r["data"]["contract_hash"], "design": r["data"]["design"],
                      "price_basis": r["data"]["price_basis"]} for r in jl(run / "CONTRACT_VERSIONS.jsonl")],
        "commitments": [{k: r["data"].get(k) for k in ("owner", "contract_hash", "decision", "policy_verdict", "agent_decision",
                                                         "rationale")} for r in jl(run / "OWNER_COMMITMENTS.jsonl")],
        "executions": [{"owner": r["data"]["owner"], "action": r["data"]["action"], "target": r["data"].get("target"),
                        "verdict": r["data"]["verdict"]} for r in jl(run / "RECEIPTS.jsonl")],
        "planner": [{"decision": r["data"].get("decision"), "response_id": r["data"].get("response_id")} for r in hub_md],
        "shock": [r for r in full if r["kind"] == "PRICE_SHOCK_INJECTED"],
        "hub_result": js(run / "HUB_RESULT.json"), "judge": js(run / "JUDGE_RESULT.json"),
        "paypal": js(run / "PAYPAL_STATUS.json") or {"mode": "NOT_RUN", "note": "No PayPal Sandbox effect in this run"},
        "worlds": js(Path(worlds) / "PER_WORLD_SUMMARY.json") if worlds else None,
        "negatives": (js(Path(negatives) / "NEGATIVE_RESULTS.json") or {}).get("summary") if negatives else None,
        "comparators": js(comparators) if comparators else None,
        "live": js(run / "LIVE_ENDPOINTS.json")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--worlds")
    ap.add_argument("--negatives")
    ap.add_argument("--comparators")
    a = ap.parse_args()
    attacker = crypto.KeyPair()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *x):
            pass

        def _send(self, code, body, ctype="application/json"):
            b = body if isinstance(body, bytes) else json.dumps(body, sort_keys=True, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/":
                return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
            if self.path == "/api/state":
                return self._send(200, snapshot(a.run, a.worlds, a.negatives, a.comparators))
            return self._send(404, {})

        def do_POST(self):
            if self.path == "/api/negative":
                live = js(Path(a.run) / "LIVE_ENDPOINTS.json")
                if not live:
                    return self._send(200, {"mode": "REPLAY", "result": "negative button needs a LIVE run (--keep)"})
                f = live["owners"]["owner:f1"]
                env = attacker.sign(crypto.DOMAINS["request"], {"request_id": new_id("req"), "fields": ["unit_cost_cents"],
                                                               "purpose": "negotiation", "grant": None, "issued_at": now(),
                                                               "nonce": os.urandom(12).hex()})
                req = urllib.request.Request(f + "/query", data=json.dumps({"envelope": env}).encode(), method="POST",
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    res = json.loads(r.read())
                return self._send(200, {"mode": "LIVE", "request": "unregistered peer asks factory for unit_cost_cents",
                                        "result": res})
            return self._send(404, {})

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    print(json.dumps({"dashboard": f"http://127.0.0.1:{a.port}/"}), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
