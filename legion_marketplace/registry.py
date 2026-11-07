# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Veraxis. Independently authored.
"""Marketplace intent registry (separate OS process).

POST /intents      owner-signed Opportunity + owner-signed discovery grant (verified against trust roots)
POST /revoke       owner-signed revocation of an intent
GET  /opportunities  run the solver over live intents (no hardcoded coalition)
GET  /view         public projection for the dashboard
The registry stores only published projections; it holds no owner secrets and no spending authority.
"""
import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from legion_federation import crypto, schemas
from legion_federation.journal import Journal
from legion_federation.canonical import sha256_hex

from . import matcher

STRUCTURAL = {"schema", "intent_id", "owner_id", "owner_pseudonym", "peer_id", "kind", "valid_until", "epoch", "grant_id", "version"}


class Registry:
    def __init__(self, state_dir):
        self.keys, self.owner_of = {}, {}
        self.intents, self.revoked = {}, set()
        self.pub = Journal(os.path.join(state_dir, "INTENT_PUBLICATIONS.jsonl"), "marketplace")
        self.disc = Journal(os.path.join(state_dir, "DISCOVERY_TRACE.jsonl"), "marketplace")
        self.matches = Journal(os.path.join(state_dir, "MATCHES.jsonl"), "marketplace")
        self.lock = threading.Lock()

    def trust(self, keys):
        for owner, pub in keys.items():
            kid = crypto.key_id(pub)
            self.keys[kid], self.owner_of[kid] = pub, owner

    def publish(self, env, grant):
        reasons = []
        try:
            o = crypto.verify(env, crypto.DOMAINS["opportunity"], trusted=self.keys)
            g = crypto.verify(grant, crypto.DOMAINS["grant"], trusted=self.keys)
            signer = self.owner_of[env["signer"]["key_id"]]
            if signer != o["owner_id"]:
                reasons.append("intent owner_id differs from signer (cross-owner intent mutation)")
            if self.owner_of[grant["signer"]["key_id"]] != o["owner_id"] or g["grantor_owner_id"] != o["owner_id"]:
                reasons.append("grant not issued by intent owner")
            if g["recipient"] != "marketplace" or g["purpose"] != "discovery":
                reasons.append("grant does not authorize marketplace discovery")
            if g["grant_id"] != o["grant_id"]:
                reasons.append("intent not bound to this grant")
            extra = set(o) - STRUCTURAL - set(g["fields"])
            if extra:
                reasons.append(f"fields published without grant: {sorted(extra)}")
            if time.time() > min(o["valid_until"], g["expires_at"]):
                reasons.append("expired")
            if not schemas.is_valid("Opportunity", o):
                reasons.append("schema invalid")
        except (crypto.VerifyError, KeyError) as exc:
            o, reasons = env.get("payload") or {}, [f"identity: {exc}"]
        verdict = "T" if not reasons else "F"
        self.pub.emit("INTENT_PUBLICATION", verdict=verdict, reasons=reasons, intent_id=o.get("intent_id"),
                      owner_id=o.get("owner_id"), intent_kind=o.get("kind"), intent_sha256=sha256_hex(o) if o else None)
        if verdict == "T":
            with self.lock:
                self.intents[o["intent_id"]] = {"payload": o, "envelope": env}
        return {"verdict": verdict, "reasons": reasons, "intent_id": o.get("intent_id")}

    def revoke(self, env):
        try:
            p = crypto.verify(env, crypto.DOMAINS["opportunity"], trusted=self.keys)
            cur = self.intents.get(p["revoke_intent_id"])
            if cur and self.owner_of[env["signer"]["key_id"]] == cur["payload"]["owner_id"]:
                self.revoked.add(p["revoke_intent_id"])
                self.pub.emit("INTENT_REVOKED", intent_id=p["revoke_intent_id"])
                return {"verdict": "T"}
            return {"verdict": "F", "reason": "not the owner"}
        except (crypto.VerifyError, KeyError) as exc:
            return {"verdict": "F", "reason": str(exc)}

    def live(self):
        t = time.time()
        return [v["payload"] for k, v in self.intents.items() if k not in self.revoked and v["payload"]["valid_until"] > t]

    def opportunities(self):
        live = self.live()
        self.disc.emit("DISCOVERY_RUN", live_intents=[i["intent_id"] for i in live],
                       by_kind={k: sum(i["kind"] == k for i in live) for k in ("demand", "supply", "service")})
        props, rejected = matcher.solve(live)
        orc = matcher.oracle(live, props)
        self.matches.emit("MATCH_RESULT", proposals=props, rejected=rejected, oracle=orc)
        return {"proposals": props, "rejected": rejected, "oracle": orc, "intents": live}


def handler(reg, admin_token):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            b = json.dumps(obj, sort_keys=True).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/opportunities":
                return self._send(200, reg.opportunities())
            if self.path == "/view":
                return self._send(200, {"intents": reg.live(), "revoked": sorted(reg.revoked)})
            return self._send(404, {})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/admin/trust":
                if self.headers.get("X-Token") != admin_token:
                    return self._send(403, {})
                reg.trust(body["keys"])
                return self._send(200, {"ok": True})
            if self.path == "/admin/shutdown":
                if self.headers.get("X-Token") != admin_token:
                    return self._send(403, {})
                self._send(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if self.path == "/intents":
                return self._send(200, reg.publish(body.get("envelope") or {}, body.get("grant") or {}))
            if self.path == "/revoke":
                return self._send(200, reg.revoke(body.get("envelope") or {}))
            return self._send(404, {})
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--state-dir", required=True)
    a = ap.parse_args()
    reg = Registry(a.state_dir)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), handler(reg, os.environ["LMF_ADMIN_TOKEN"]))
    print(json.dumps({"ready": True, "pid": os.getpid()}), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
