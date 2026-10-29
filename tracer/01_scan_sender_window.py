import json, sys, time, urllib.request, concurrent.futures as cf
from datetime import datetime, timezone

RPC = "https://ethereum-rpc.publicnode.com"
BINANCE14 = "0x28c6c06298d514db089934071355e5743bf21d60"

def rpc(method, params):
    body = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    req = urllib.request.Request(RPC, data=body, headers={"content-type":"application/json","user-agent":"antibody-tracer/0.1 (Hasky Labs chain forensics)","accept":"*/*"})
    for _ in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))["result"]
        except Exception as e:
            time.sleep(1)
    return None

def block(n, full=False):
    return rpc("eth_getBlockByNumber", [hex(n), full])

def ts(b): return int(b["timestamp"], 16)

# binary search block at target time
def block_at(target):
    hi = int(rpc("eth_blockNumber", []), 16); lo = hi - 20000
    while lo < hi:
        mid = (lo+hi)//2
        if ts(block(mid)) < target: lo = mid+1
        else: hi = mid
    return lo

t0 = int(datetime(2026,10,29,20,10,tzinfo=timezone.utc).timestamp())
t1 = int(datetime(2026,10,29,21,15,tzinfo=timezone.utc).timestamp())
b0, b1 = block_at(t0), block_at(t1)
print(f"scanning blocks {b0}..{b1} ({b1-b0} blocks)", file=sys.stderr)

out = []
def work(n):
    b = block(n, True)
    if not b: return []
    r = []
    for tx in b["transactions"]:
        if tx["from"].lower() == BINANCE14:
            r.append({"block":n,"time":datetime.fromtimestamp(ts(b),timezone.utc).strftime("%H:%M:%S"),
                      "hash":tx["hash"],"to":tx["to"],"value_eth":int(tx["value"],16)/1e18,
                      "input_sel":tx["input"][:10],"input_len":len(tx["input"])})
    return r

with cf.ThreadPoolExecutor(12) as ex:
    for r in ex.map(work, range(b0, b1+1)):
        out.extend(r)

json.dump(out, open("evidence/binance14_outflows.json","w"), indent=1)
print(f"{len(out)} txs from Binance 14 in window", file=sys.stderr)
for t in out: print(t["time"], t["to"], f"{t['value_eth']:.2f} ETH", t["input_sel"], t["hash"])
