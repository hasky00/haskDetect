#!/usr/bin/env python3
"""Case 002: pull every transaction touching a Bitcoin address from a public
mempool.space-compatible API and summarise sweep-in / cash-out behaviour.

    python3 05_btc_address_sweeps.py bc1p0f7wmcnesrapznymf9ljdn04pudgmh96sqtrm9vmgqxdh666fh8qvn63r7

Plain Python, no API keys. Writes <addr>_txs.json next to the script's cwd.
"""
import sys, json, time, datetime, collections, urllib.request

API = "https://mempool.space/api"
UA = {"User-Agent": "HaskDetect/0.1 (chain forensics; hasky00.github.io/haskDetect)"}

def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(2 * (i + 1))
    raise SystemExit(f"gave up: {url}")

def pull(addr):
    txs = get(f"{API}/address/{addr}/txs")
    while txs:
        page = get(f"{API}/address/{addr}/txs/chain/{txs[-1]['txid']}")
        if not page:
            break
        txs += page
        if len(page) < 25:
            break
        time.sleep(0.4)
    return list({t["txid"]: t for t in txs}.values())

def ts(t):
    return datetime.datetime.fromtimestamp(t["status"]["block_time"], datetime.UTC)

def main(addr):
    txs = pull(addr)
    json.dump(txs, open(f"{addr}_txs.json", "w"))
    conf = [t for t in txs if t["status"].get("confirmed")]
    inc = [t for t in conf if addr not in {v["prevout"]["scriptpubkey_address"] for v in t["vin"]}]
    out = [t for t in conf if t not in inc]
    inc.sort(key=lambda t: t["status"]["block_time"])
    recv = lambda t: sum(o["value"] for o in t["vout"] if o["scriptpubkey_address"] == addr)
    print(f"{len(txs)} txs  incoming {len(inc)}  outgoing {len(out)}  unconfirmed {len(txs)-len(conf)}")
    print("first in ", ts(inc[0]), inc[0]["txid"])
    print("last in  ", ts(inc[-1]), inc[-1]["txid"])
    print("received BTC", sum(map(recv, inc)) / 1e8)
    senders = {v["prevout"]["scriptpubkey_address"] for t in inc for v in t["vin"]}
    print("distinct input addresses", len(senders))
    vals = sorted(map(recv, inc))
    print("sweep size sat  min/median/max", vals[0], vals[len(vals) // 2], vals[-1])
    hist = collections.Counter(ts(t).strftime("%d %b %Hh") for t in inc)
    print("\nsweeps per hour (UTC)")
    for k in sorted(hist, key=lambda k: datetime.datetime.strptime(k, "%d %b %Hh")):
        print(f"  {k}  {hist[k]:3d}  {'#' * hist[k]}")
    print("\noutgoing")
    for t in sorted(out, key=lambda t: t["status"]["block_time"]):
        dests = [(o["scriptpubkey_address"], o["value"] / 1e8) for o in t["vout"] if o["scriptpubkey_address"] != addr]
        print(" ", ts(t), t["txid"][:16], f"inputs={len(t['vin'])}", dests)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bc1p0f7wmcnesrapznymf9ljdn04pudgmh96sqtrm9vmgqxdh666fh8qvn63r7")
