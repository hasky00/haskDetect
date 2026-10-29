# HaskDetect

Chain forensics for crypto crime investigators, by Hasky Labs. Behaviour-based detection: score what an address *does*, not what a label says it is.

Every case here is reconstructed from raw node data and published with the hashes, so anyone can check the work.

## Cases

| # | Case | Date | Status |
|---|------|------|--------|
| 001 | [Binance hot wallet drain via EIP-7702 backdoor](cases/001-binance-hot-wallet/) | 29 Oct 2026 | Open, backdoor live at time of writing |

Read the case file: **[cases/001-binance-hot-wallet/index.html](cases/001-binance-hot-wallet/index.html)** (or via GitHub Pages once enabled).

## Case 001 in brief

An attacker holding the private key to Binance hot wallet `0x28C6c06298d514Db089934071355E5743bf21d60` used EIP-7702 to install their own contract code onto the account, then called `sweep(to, tokens[65])` once. 167,464 ETH and 1.615B USDT left in a single transaction. Fifty authorizations with fifty consecutive nonces were submitted to beat the wallet's ten-second nonce churn. The technique was rehearsed three times on throwaway accounts earlier the same day.

Key hashes:

- Set-code tx (50 authorizations): `0xad99264d5532ae0dd04b2004eebda05f25657e70dacb764f7ac8d4ccd051298b`
- Sweep tx: `0x53bd38b816c23e74134786c29a8c18d792777998a3b9326047b583100e88e2f3`
- Attacker signer: `0x7c8601d4645b93cea45f71e118a729332e6b5ca0`
- Attacker code: `0x63e842b054bd624a465454d533c33f573e9c6fae`
- Loot: `0x5227f603c1ee34ce3c06efe6477003bdfccb2f8c`
- 195,460 ETH parked: `0x8532FA14ACAf483729C449b8458aedDb900543D4`

## Tracer scripts

Plain Python, public RPC, no API keys.

```
pip install eth-account rlp
cd cases/001-binance-hot-wallet
python3 ../../tracer/01_scan_sender_window.py       # every tx sent by the victim in the attack window
python3 ../../tracer/02_transfers_from_victim.py    # every Transfer event with the victim as sender
python3 ../../tracer/03_recover_7702_signers.py     # recover signers from a type-4 tx's authorization list
```

Scripts send a plain `User-Agent` identifying HaskDetect. Some public nodes reject requests with no UA.

## Detection signals from Case 001

1. Signer account younger than 24 hours
2. Gas funded by an internal transfer with no sender history (mixer shape)
3. Same function selector rehearsed on throwaway accounts hours before
4. Type-4 transaction whose authorization signer is a high-value account, submitted by an unrelated fresh account
5. Delegate contract deployed the same day by the submitter
6. Set-code to sweep gap under five minutes

Signals 4 and 5 did not exist before Pectra. Most monitoring does not look for them yet.

## Evidence

`cases/001-binance-hot-wallet/evidence/` holds the raw JSON pulled from the chain and Blockscout at the time of writing. Treat it as a snapshot; re-run the scripts for current state.

---

© 2026 Hasky Labs, Copenhagen. All rights reserved. Made by Hasky Labs, Copenhagen.
