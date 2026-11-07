# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Veraxis. Independently authored.
"""Seven-collective first-attempt E2E (WO-LMF-006) and its comparator arms.

Processes: 7 owner peers + marketplace registry + federation coordinator + independent Judge,
all separate OS processes. This orchestrator plays only the *environment*: it starts processes,
distributes public keys (out-of-band trust roots), injects the preregistered supplier shock and
collects evidence. It holds no owner key and makes no owner decision.

Usage: python -m legion_marketplace.e2e --core <LEGION> --out <dir> --arm A2|A1 [--dashboard-port 8790]
"""
import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import scenario

FED_ROOT = Path(os.environ.get("LMF_FEDERATION_ROOT", Path(__file__).resolve().parents[2] / "LEGION-Federation"))
MKT_ROOT = Path(__file__).resolve().parents[1]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def post(url, body, token=None, timeout=120):
    h = {"Content-Type": "application/json"}
    if token:
        h["X-Token"] = token
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def get(url, token=None, timeout=60):
    req = urllib.request.Request(url, headers={"X-Token": token} if token else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class Env:
    def __init__(self, core, out, arm, shock=True):
        self.core, self.out, self.arm, self.shock = Path(core), Path(out), arm, shock
        self.out.mkdir(parents=True, exist_ok=True)
        self.admin, self.reader = secrets.token_hex(16), secrets.token_hex(16)
        self.procs, self.events = {}, []
        self.lock = threading.Lock()
        self.status = {"arm": arm, "phase": "STARTING"}

    def log(self, kind, **d):
        rec = {"t": time.time(), "kind": kind, **d}
        with self.lock:
            self.events.append(rec)
            with open(self.out / "FULL_TRACE.jsonl", "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def spawn(self, name, args, cwd, extra_env=None):
        env = dict(os.environ, LMF_ADMIN_TOKEN=self.admin, LMF_READER_TOKEN=self.reader,
                   PYTHONPATH=os.pathsep.join([str(FED_ROOT), str(MKT_ROOT)]), **(extra_env or {}))
        p = subprocess.Popen([sys.executable, *args], cwd=str(cwd), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=open(self.out / f"{name.replace(':', '_')}.stderr.txt", "w"), text=True)
        ready = json.loads(p.stdout.readline())
        self.procs[name] = p
        self.log("PROCESS_STARTED", name=name, pid=p.pid, ready=ready)
        return p, ready

    def start(self):
        ports = {o: free_port() for o in ["owner:b1", "owner:b2", "owner:b3", "owner:b4", "owner:b5", "owner:f1", "owner:e1"]}
        key_root = Path(os.environ["LOCALAPPDATA"]) / "Veraxis" / "LMF" / self.out.name
        self.cfgs = scenario.owner_configs(self.core, self.out / "owners", ports, key_root)
        self.ep = {o: f"http://127.0.0.1:{p}" for o, p in ports.items()}
        pubs = {}
        for o, cfg in self.cfgs.items():
            path = self.out / f"config_{o.split(':')[1]}.json"
            path.write_text(json.dumps(cfg, indent=1))
            _, ready = self.spawn(o, ["-m", "legion_federation.owner_peer", "--config", str(path)], FED_ROOT,
                                  {"LMF_NIM_KEY_FILE": os.environ.get("LMF_NIM_KEY_FILE", "")})
            pubs[o] = ready["pub"]
        self.pubs = pubs
        if self.arm in ("A2", "A3"):
            self.mport = free_port()
            self.spawn("marketplace", ["-m", "legion_marketplace.registry", "--port", str(self.mport),
                                       "--state-dir", str(self.out / "marketplace")], MKT_ROOT)
            (self.out / "marketplace").mkdir(exist_ok=True)
            self.mkt = f"http://127.0.0.1:{self.mport}"
            post(self.mkt + "/admin/trust", {"keys": pubs}, self.admin)
        (self.out / "TRUST_ROOTS.json").write_text(json.dumps({"note": "out-of-band demo registrar: owner -> Ed25519 public key "
                                                                       "as read from each owner's own process", "keys": pubs}, indent=1))

    def env_hook_server(self):
        env = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n) or b"{}")
                fired = False
                if body.get("stage") == "first_version_offered" and env.shock:
                    r = post(env.ep["owner:f1"] + "/admin/event", {"event": "ev-supplier-shock"}, env.admin)
                    fired = r.get("fired", False)
                    env.log("PRICE_SHOCK_INJECTED", by="environment", at_stage=body["stage"],
                            contract_hash=body.get("contract_hash"), factory_response=r)
                    env.status["phase"] = "PRICE_SHOCK"
                b = json.dumps({"shock_fired": fired}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
        self.hook_port = free_port()
        srv = ThreadingHTTPServer(("127.0.0.1", self.hook_port), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self.hook_port}/hook"

    def run(self, proposal_file=None):
        self.start()
        hook = self.env_hook_server()
        self.status["phase"] = "PUBLISHING"
        if self.arm in ("A2", "A3"):
            for o in self.cfgs:
                r = post(self.ep[o] + "/admin/publish", {"marketplace": self.mkt}, self.admin)
                self.log("OWNER_PUBLISHED", owner=o, marketplace_verdict=r["marketplace"]["verdict"],
                         intent_id=r["intent"]["intent_id"])
        (self.out / "endpoints.json").write_text(json.dumps(self.ep))
        args = ["-m", "legion_federation.hub", "--out", str(self.out), "--endpoints", str(self.out / "endpoints.json"),
                "--env-hook", hook, "--arm", self.arm]
        if self.arm == "A2":
            args += ["--marketplace", self.mkt]
        else:
            if proposal_file is None:  # A1: counterparts pre-known by address; no marketplace, no discovery
                c = self.cfgs
                prop = {"proposal_id": "prop-A1-known-peers", "spec_hash": scenario.SPEC_HASH, "class": "sensor-module",
                        "quantity": 100,
                        "buyers": [{"intent_id": f"known-{b}", "owner_id": f"owner:{b}", "peer_id": f"peer:{b}", "quantity": 20,
                                    "max_payment_cents": c[f"owner:{b}"]["public"]["max_payment_cents"]} for b in scenario.BUYERS],
                        "factory": {"intent_id": "known-f1", "owner_id": "owner:f1", "peer_id": "peer:f1", "minimum_quantity": 100},
                        "engineer": {"intent_id": "known-e1", "owner_id": "owner:e1", "peer_id": "peer:e1"},
                        "note": "A1 arm: counterpart addresses configured in advance (no discovery)"}
                proposal_file = str(self.out / "A1_KNOWN_PEERS_PROPOSAL.json")
                Path(proposal_file).write_text(json.dumps(prop, indent=1))
            args += ["--proposal", proposal_file]
        self.status["phase"] = "NEGOTIATING"
        hub, ready = self.spawn("coordinator:hub", args, FED_ROOT, {"LMF_NIM_KEY_FILE": os.environ.get("LMF_NIM_KEY_FILE", "")})
        keys = dict(self.pubs, **{"coordinator:hub": ready["pub"]})
        for o in self.cfgs:
            post(self.ep[o] + "/admin/trust", {"keys": keys, "endpoints": self.ep}, self.admin)
        hub.stdin.write("GO\n")
        hub.stdin.flush()
        line = hub.stdout.readline()
        hub.wait(timeout=60)
        res = json.loads(line) if line.strip() else {"outcome": "HUB_CRASHED"}
        self.log("HUB_FINISHED", result=res)
        self.status["phase"] = "JUDGING"
        jr = subprocess.run([sys.executable, "-m", "legion_marketplace.judge", "--run", str(self.out),
                             "--manifest", str(MKT_ROOT / "RUN_MANIFEST.json")],
                            cwd=str(MKT_ROOT), env=dict(os.environ, LMF_READER_TOKEN=self.reader,
                                                        PYTHONPATH=os.pathsep.join([str(FED_ROOT), str(MKT_ROOT)])),
                            capture_output=True, text=True, timeout=300)
        (self.out / "judge_stdout.txt").write_text(jr.stdout + jr.stderr)
        self.log("JUDGE_FINISHED", returncode=jr.returncode, tail=jr.stdout[-500:])
        self.status["phase"] = "DONE"
        return res

    def stop(self):
        for o in getattr(self, "cfgs", {}):
            try:
                post(self.ep[o] + "/admin/shutdown", {}, self.admin, timeout=5)
            except Exception:
                pass
        if hasattr(self, "mkt"):
            try:
                post(self.mkt + "/admin/shutdown", {}, self.admin, timeout=5)
            except Exception:
                pass
        for p in self.procs.values():
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", default="A2", choices=["A1", "A2"])
    ap.add_argument("--proposal", default=None)
    ap.add_argument("--keep", action="store_true", help="keep peers alive after the run (dashboard/negative tests)")
    a = ap.parse_args()
    env = Env(a.core, a.out, a.arm)
    try:
        res = env.run(a.proposal)
        print(json.dumps(res), flush=True)
        if a.keep:
            (Path(a.out) / "LIVE_ENDPOINTS.json").write_text(json.dumps({"owners": env.ep, "marketplace": getattr(env, "mkt", None)}))
            input()
    finally:
        env.stop()


if __name__ == "__main__":
    main()
