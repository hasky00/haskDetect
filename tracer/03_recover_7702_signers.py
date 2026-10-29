"""Recover the signer of every EIP-7702 authorization in a type-4 transaction.

Usage:  python3 03_recover_7702_signers.py <tx_hash>

An authorization is a signature over keccak(0x05 || rlp([chainId, address, nonce])).
Whoever signed it held that account's private key. For Case 001 this proves the
Binance 14 key was in the attacker's hands fifty times over.

pip install eth-account rlp
"""
import json, sys, urllib.request
import rlp
from eth_keys import keys
from eth_utils import keccak, to_checksum_address

RPC = "https://ethereum-rpc.publicnode.com"
UA = "haskdetect-tracer/0.1 (Hasky Labs chain forensics)"

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, data=body, headers={"content-type": "application/json", "user-agent": UA, "accept": "*/*"})
    return json.load(urllib.request.urlopen(req, timeout=60))["result"]

def main(tx_hash):
    tx = rpc("eth_getTransactionByHash", [tx_hash])
    if tx.get("type") != "0x4":
        sys.exit(f"not a type-4 (EIP-7702) transaction: type={tx.get('type')}")
    auths = tx["authorizationList"]
    print(f"{len(auths)} authorizations, submitted by {tx['from']}\n")
    for a in auths:
        msg = b"\x05" + rlp.encode([int(a["chainId"], 16), bytes.fromhex(a["address"][2:]), int(a["nonce"], 16)])
        sig = keys.Signature(vrs=(int(a["yParity"], 16), int(a["r"], 16), int(a["s"], 16)))
        signer = to_checksum_address(sig.recover_public_key_from_msg_hash(keccak(msg)).to_address())
        code = rpc("eth_getCode", [signer, "latest"])
        live = "DELEGATION STILL LIVE" if code.lower().startswith("0xef0100" + a["address"][2:].lower()) else ""
        print(f"signer={signer} nonce={int(a['nonce'],16):,} delegate={a['address']} {live}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "0xad99264d5532ae0dd04b2004eebda05f25657e70dacb764f7ac8d4ccd051298b")
