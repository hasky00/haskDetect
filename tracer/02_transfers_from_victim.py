import json, sys, time, urllib.request
from collections import defaultdict
from datetime import datetime, timezone

RPC = "https://ethereum-rpc.publicnode.com"
import concurrent.futures as cf
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
B14 = "0x28c6c06298d514db089934071355e5743bf21d60"
USDT="0xdac17f958d2ee523a2206206994597c13d831ec7"; USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
pad = lambda a: "0x"+"0"*24+a[2:]

def rpc(method, params):
    body = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    req = urllib.request.Request(RPC, data=body, headers={"content-type":"application/json","user-agent":"antibody-tracer/0.1 (Hasky Labs chain forensics)","accept":"*/*"})
    for _ in range(4):
        try:
            j=json.load(urllib.request.urlopen(req, timeout=60))
            if "error" in j: print("rpc err",j["error"],file=sys.stderr); return None
            return j["result"]
        except Exception as e: time.sleep(1)
    return None

txs = json.load(open("evidence/binance14_outflows.json"))
b0 = min(t["block"] for t in txs)-50; b1 = max(t["block"] for t in txs)+50
print(f"getLogs Transfer from Binance14, blocks {b0}..{b1}", file=sys.stderr)
logs=[]
def blk(n):
    r=rpc("eth_getBlockReceipts",[hex(n)]) or []
    out=[]
    for rc in r:
        for lg in rc["logs"]:
            if len(lg["topics"])==3 and lg["topics"][0]==TRANSFER and lg["topics"][1]==pad(B14): out.append(lg)
    return out
with cf.ThreadPoolExecutor(10) as ex:
    for r in ex.map(blk, range(b0,b1+1)): logs+=r
print(len(logs),"transfer logs", file=sys.stderr)

by_tx=defaultdict(lambda:{"tokens":set(),"to":set(),"usdt":0,"usdc":0,"block":0})
by_to=defaultdict(lambda:{"tokens":set(),"usdt":0,"usdc":0,"txs":set()})
for lg in logs:
    if len(lg["topics"])<3: continue
    to="0x"+lg["topics"][2][-40:]; tok=lg["address"].lower(); h=lg["transactionHash"]
    amt=int(lg["data"],16) if lg["data"] not in ("0x","") else 0
    d=by_tx[h]; d["tokens"].add(tok); d["to"].add(to); d["block"]=int(lg["blockNumber"],16)
    e=by_to[to]; e["tokens"].add(tok); e["txs"].add(h)
    if tok==USDT: d["usdt"]+=amt/1e6; e["usdt"]+=amt/1e6
    if tok==USDC: d["usdc"]+=amt/1e6; e["usdc"]+=amt/1e6

print("\nTxs moving tokens OUT of Binance 14, ranked by distinct tokens:")
for h,d in sorted(by_tx.items(), key=lambda kv:(-len(kv[1]["tokens"]),-kv[1]["usdt"]))[:10]:
    tx=rpc("eth_getTransactionByHash",[h])
    print(f"blk {d['block']} {h}\n   tokens={len(d['tokens'])} recipients={len(d['to'])} USDT={d['usdt']:,.0f} USDC={d['usdc']:,.0f}\n   tx.from={tx['from']} tx.to={tx['to']} sel={tx['input'][:10]} value={int(tx['value'],16)/1e18:.2f} ETH")

print("\nRecipients ranked:")
for a,e in sorted(by_to.items(), key=lambda kv:(-len(kv[1]["tokens"]),-kv[1]["usdt"]-kv[1]["usdc"]))[:10]:
    print(f"{a} tokens={len(e['tokens'])} USDT={e['usdt']:,.0f} USDC={e['usdc']:,.0f} txs={len(e['txs'])}")
json.dump({"by_tx":{h:{"tokens":sorted(d["tokens"]),"to":sorted(d["to"]),"usdt":d["usdt"],"usdc":d["usdc"],"block":d["block"]} for h,d in by_tx.items()},
           "by_to":{a:{"tokens":sorted(e["tokens"]),"usdt":e["usdt"],"usdc":e["usdc"],"txs":sorted(e["txs"])} for a,e in by_to.items()}},
          open("evidence/transfers_from_b14.json","w"), indent=1)
