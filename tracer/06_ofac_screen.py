#!/usr/bin/env python3
"""Case 002: screen addresses against OFAC's sanctioned digital-currency list.

    python3 06_ofac_screen.py addr1 [addr2 ...]
    python3 06_ofac_screen.py --parked          # screen the Case 002 parked lots
    python3 06_ofac_screen.py --parked --hop     # also screen their one-hop destinations

Source: OFAC SDN digital-currency addresses, mirrored per-asset by the
0xB10C/ofac-sanctioned-digital-currency-addresses repo (derived from the
official Treasury SDN list). Bitcoin addresses live in the XBT list.
No API keys. Read-only.
"""
import sys, json, time, urllib.request

RAW = "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists/sanctioned_addresses_{}.txt"
ASSETS = ["XBT", "ETH", "LTC", "XMR", "USDT", "USDC", "BCH", "DASH", "ZEC"]
MP = "https://mempool.space/api"
UA = {"User-Agent": "HaskDetect/0.1 (chain forensics; hasky00.github.io/haskDetect)"}

# Case 002 parked cash-out lots (unspent as of 2 Nov 2026 09:00 UTC)
PARKED = [
    "bc1qn3fze9w3c0m38y84v76qr2z5dz9cjx0hz4aeva",
    "bc1q8hyw6c47t4cskvn655csdc8ym7wc7tcnj6ws4j",
    "bc1q8q4aqg9fyxch0k48wf2xcuqdfaqpc55un0mnsc",
    "bc1qjdqn0tqm4agmsq5njss2snuanyqu54mjkjm8gr",
    "bc1qwurqa0yzggsurz86mku3dqnf5pdnjkq0089vvt",
    "bc1qvc9lyhulpfup3r57nphttsdqdn8tdyxs4wp2mv",
    "bc1qn63tuet8rsnlhlql9m6vnx0uh8sse6nhlvl2pa",
    "bc1qvlf4z70mrjssejvyk94fmxte3lj0xqepy7kxsz",
    "bc1qzndsy3lel04ayyfmhfcw3sw4wc0jh0ykgulpr3",
    "bc1q5ryspczuxjkgtglm6nx9ejdv82fjfdmxa2dklr",
    "bc1qglppv5dv7cvah6c8xewz8ssp0syaparkrz49jd",
    "bc1qlea5p4c4vxjs0vul23muv9qys8nmvx526u9v4j",
    "bc1qk2ssf2cumr3dugq46c8qvl7008584f4h8wgjhl",
    "bc1qnp67a8zfeenmlvqwsy8ffkyz5pxrrxtkvu3u9p",
    "bc1q4lwqjw5870wf8v3uw6dlsc97ws50fg53xkrxnr",
    "bc1qwek0k639s8hmcvc5sxu4jqzf832mdhec7sxxnt",
]

def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40)

def load_ofac():
    sanctioned = {}
    for a in ASSETS:
        try:
            for line in fetch(RAW.format(a)).read().decode().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    sanctioned[line] = a
                    sanctioned[line.lower()] = a
        except Exception:
            pass
    return sanctioned

def spends_to(addr):
    """Return list of output addresses this address has paid (one hop)."""
    try:
        txs = json.load(fetch(f"{MP}/address/{addr}/txs"))
    except Exception:
        return []
    outs = []
    for t in txs:
        if addr in {v.get("prevout", {}).get("scriptpubkey_address") for v in t["vin"]}:
            for o in t["vout"]:
                a = o.get("scriptpubkey_address")
                if a and a != addr:
                    outs.append(a)
    return sorted(set(outs))

def main(argv):
    hop = "--hop" in argv
    if "--parked" in argv:
        targets = PARKED
    else:
        targets = [a for a in argv if not a.startswith("--")]
    if not targets:
        print("usage: 06_ofac_screen.py <addr...> | --parked [--hop]"); return
    ofac = load_ofac()
    print(f"loaded {len(ofac)//2} OFAC sanctioned addresses across {len(ASSETS)} assets\n")
    hits = []
    for addr in targets:
        if addr in ofac:
            hits.append((addr, addr, ofac[addr]))
            print(f"HIT  {addr}  is OFAC-listed ({ofac[addr]})")
            continue
        print(f"ok   {addr}  not listed", end="")
        if hop:
            dests = spends_to(addr)
            flagged = [d for d in dests if d in ofac]
            if dests:
                print(f"  (spent to {len(dests)} addr; checking)")
                for d in flagged:
                    hits.append((addr, d, ofac[d]))
                    print(f"     HIT  {addr} -> {d}  OFAC-listed ({ofac[d]})")
            else:
                print("  (no outgoing yet)")
            time.sleep(0.3)
        else:
            print()
    print()
    print(f"RESULT: {len(hits)} OFAC hit(s)." if hits else "RESULT: no OFAC hits.")

if __name__ == "__main__":
    main(sys.argv[1:])
