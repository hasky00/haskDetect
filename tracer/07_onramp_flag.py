#!/usr/bin/env python3
"""Case 002: classify where a moved lot lands, by on-chain behaviour.

Monero itself cannot be traced. What CAN be seen is the Bitcoin-side doorway:
when a parked lot spends, what shape is the destination? This scores a
destination address as one of:

  EXCHANGE/CUSTODIAN  - high throughput, many counterparties, batched payouts
  SWAP ON-RAMP        - fast in-out turnover, brief holding, moderate volume
                        (the shape of an instant BTC->XMR / bridge deposit)
  STAGING             - fresh, low activity, holds then fans out to fresh addrs
  PARKED              - received, unspent, idle

Plus an optional watchlist (KNOWN_ONRAMPS) for addresses already attributed by
hand. Behaviour is the primary signal; the list is a convenience, never relied
on, because swap services rotate deposit addresses constantly.

    python3 07_onramp_flag.py <addr> [<addr> ...]

Public mempool.space API, no keys, read-only. Note: /txs returns only the most
recent page, so this is tuned for small fresh destination addresses (the parked
lots and their one-hop outputs), not for high-tx-count addresses like the
collector, which need the full-history pull in tracer/05 first.
"""
import sys, json, time, datetime, urllib.request

MP = "https://mempool.space/api"
UA = {"User-Agent": "HaskDetect/0.1 (chain forensics; hasky00.github.io/haskDetect)"}

# Hand-attributed on-ramp / bridge deposit addresses go here as they are found.
# Kept deliberately empty by default: an unverified list is worse than none.
KNOWN_ONRAMPS = {
    # "bc1q...": "ChangeNOW BTC->XMR deposit (attributed 2026-11-xx)",
}

def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(MP + path, headers=UA), timeout=40))

def age_hours(first_bt, last_bt):
    return max(0.0, (last_bt - first_bt) / 3600.0)

def classify(addr):
    info = get(f"/address/{addr}")
    cs = info["chain_stats"]
    recv = cs["funded_txo_sum"]; sent = cs["spent_txo_sum"]
    bal = recv - sent; ntx = cs["tx_count"]
    in_n = cs["funded_txo_count"]; out_n = cs["spent_txo_count"]
    if ntx == 0:
        return "EMPTY", {"note": "no history"}
    txs = get(f"/address/{addr}/txs")
    conf = [t for t in txs if t["status"].get("confirmed")]
    times = [t["status"]["block_time"] for t in conf]
    held_h = age_hours(min(times), max(times)) if times else 0.0
    # counterparties
    senders, receivers = set(), set()
    fresh_out = 0; total_out = 0
    for t in conf:
        is_out = addr in {v.get("prevout", {}).get("scriptpubkey_address") for v in t["vin"]}
        if is_out:
            for o in t["vout"]:
                a = o.get("scriptpubkey_address")
                if a and a != addr:
                    receivers.add(a); total_out += 1
        else:
            for v in t["vin"]:
                a = v.get("prevout", {}).get("scriptpubkey_address")
                if a: senders.add(a)
    turnover = (sent / recv) if recv else 0.0   # fraction already forwarded
    sig = {
        "recv_btc": round(recv / 1e8, 4), "bal_btc": round(bal / 1e8, 4),
        "tx_count": ntx, "in_cp": len(senders), "out_cp": len(receivers),
        "turnover": round(turnover, 2), "held_h": round(held_h, 1),
    }
    # --- rules, most specific first ---
    if bal == recv and sent == 0:
        return "PARKED (unspent)", sig
    if ntx >= 200 and len(senders) + len(receivers) >= 100:
        return "EXCHANGE/CUSTODIAN (high throughput)", sig
    # swap on-ramp: receives, forwards most of it quickly, modest counterparties
    if turnover >= 0.8 and held_h <= 72 and ntx <= 60 and len(receivers) >= 1:
        return "SWAP ON-RAMP shape (fast pass-through)", sig
    # staging: holds a while, then fans out to several fresh-looking addrs
    if len(receivers) >= 3 and turnover >= 0.8:
        return "STAGING (fans out)", sig
    if turnover >= 0.5:
        return "FORWARDED (needs a human look)", sig
    return "HOLDING / unclear", sig

def main(addrs):
    if not addrs:
        print("usage: 07_onramp_flag.py <addr> [<addr> ...]"); return
    for a in addrs:
        if a in KNOWN_ONRAMPS:
            print(f"{a}\n  WATCHLIST HIT: {KNOWN_ONRAMPS[a]}")
        try:
            label, sig = classify(a)
            print(f"{a}\n  {label}\n  {sig}\n")
        except Exception as e:
            print(f"{a}\n  error: {e}\n")
        time.sleep(0.3)

if __name__ == "__main__":
    main(sys.argv[1:])
