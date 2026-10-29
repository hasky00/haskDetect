"""HaskDetect watcher — Case 001.

Polls the attacker's holding addresses and the still-live backdoor, and prints
an alert line whenever balance or nonce changes (i.e. funds move). Defensive
only: it observes and reports, so a human can notify the exits (exchanges,
bridges, Tether/Circle) fast.

Run:  python3 watch.py            # one snapshot
      python3 watch.py --loop 60  # re-check every 60s, alert on change
"""
import json, sys, time, urllib.request
from datetime import datetime, timezone

RPC = "https://ethereum-rpc.publicnode.com"
UA = "haskdetect-watcher/0.1 (Hasky Labs chain forensics)"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"

# label -> address.  The ones that matter for the live race.
WATCH = {
    "parked-195k-ETH": "0x8532FA14ACAf483729C449b8458aedDb900543D4",
    "loot":            "0x5227f603c1ee34ce3c06efe6477003bdfccb2f8c",
    "attacker-signer": "0x7c8601d4645b93cea45f71e118a729332e6b5ca0",
    "binance14":       "0x28c6c06298d514db089934071355e5743bf21d60",
}

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, data=body, headers={"content-type": "application/json", "user-agent": UA, "accept": "*/*"})
    for _ in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))["result"]
        except Exception:
            time.sleep(1)
    return None

def snapshot():
    s = {}
    for label, addr in WATCH.items():
        eth = int(rpc("eth_getBalance", [addr, "latest"]), 16) / 1e18
        nonce = int(rpc("eth_getTransactionCount", [addr, "latest"]), 16)
        usdt = int(rpc("eth_call", [{"to": USDT, "data": "0x70a08231" + "0" * 24 + addr[2:]}, "latest"]), 16) / 1e6
        code = rpc("eth_getCode", [addr, "latest"])
        s[label] = {"eth": eth, "nonce": nonce, "usdt": usdt, "delegated": code.lower().startswith("0xef0100")}
    return s

def fmt(label, v):
    d = " DELEGATED" if v["delegated"] else ""
    return f"  {label:18} {v['eth']:>14,.2f} ETH  USDT {v['usdt']:>16,.0f}  nonce {v['nonce']}{d}"

def main():
    now = lambda: datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    prev = snapshot()
    print(f"[{now()}] baseline")
    for l, v in prev.items():
        print(fmt(l, v))
    if len(sys.argv) < 3 or sys.argv[1] != "--loop":
        return
    interval = int(sys.argv[2])
    while True:
        time.sleep(interval)
        cur = snapshot()
        for l in WATCH:
            a, b = prev[l], cur[l]
            if a != b:
                moved = b["eth"] - a["eth"]
                print(f"[{now()}] ** MOVEMENT ** {l}: ETH {moved:+,.2f} (nonce {a['nonce']}->{b['nonce']})")
                print(fmt(l, b))
        prev = cur

if __name__ == "__main__":
    main()
