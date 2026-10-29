// HaskDetect live watcher — Case 001
// Two layers: mempool (WebSocket, sees pending txs) + block poll (backstop for
// private-relay moves). On any balance/nonce change of a watched address it
// writes a logfile line and, if NPUB is set, sends an encrypted Nostr DM.
//
// Defensive only: it observes and alerts so a human can notify the exits fast.
//
// Run:  npm i ws nostr-tools
//       NPUB=npub1... RELAY=wss://relay.damus.io node watch.mjs
//
// Env:
//   NPUB    your npub to DM (optional; logfile-only if unset)
//   RELAY   nostr relay to publish the DM to (default wss://relay.damus.io)
//   ETH_WS  eth node websocket (default wss://ethereum-rpc.publicnode.com)
//   POLL    block-layer poll seconds (default 30)

import WebSocket from "ws";
import { finalizeEvent, generateSecretKey, getPublicKey, nip04, nip19, SimplePool } from "nostr-tools";
import { appendFileSync } from "node:fs";

const ETH_WS = process.env.ETH_WS || "wss://ethereum-rpc.publicnode.com";
const RELAY  = process.env.RELAY  || "wss://relay.damus.io";
const POLL   = (parseInt(process.env.POLL || "30", 10)) * 1000;
const LOG    = "haskdetect-alerts.log";

// Watched addresses — the live race for Case 001.
const WATCH = {
  "parked-195k-ETH": "0x8532fa14acaf483729c449b8458aeddb900543d4",
  "loot":            "0x5227f603c1ee34ce3c06efe6477003bdfccb2f8c",
  "attacker-signer": "0x7c8601d4645b93cea45f71e118a729332e6b5ca0",
  "binance14":       "0x28c6c06298d514db089934071355e5743bf21d60",
};
const SET = new Set(Object.values(WATCH));
const nameOf = (a) => Object.keys(WATCH).find((k) => WATCH[k] === a?.toLowerCase());

// --- Nostr alerting (optional) ---
let dmTo = null, botSk = null, pool = null;
if (process.env.NPUB) {
  try {
    dmTo = nip19.decode(process.env.NPUB).data;     // hex pubkey
    botSk = generateSecretKey();                     // throwaway bot identity
    pool = new SimplePool();
    log(`nostr alerts on -> DM to ${process.env.NPUB} via ${RELAY} (bot ${nip19.npubEncode(getPublicKey(botSk))})`);
  } catch (e) { log("bad NPUB, DMs disabled: " + e.message); dmTo = null; }
}

function log(line) {
  const s = `[${new Date().toISOString()}] ${line}`;
  console.log(s);
  try { appendFileSync(LOG, s + "\n"); } catch {}
}

async function alert(text) {
  log("ALERT " + text);
  if (!dmTo) return;
  try {
    const content = await nip04.encrypt(botSk, dmTo, text);
    const evt = finalizeEvent({ kind: 4, created_at: Math.floor(Date.now() / 1000), tags: [["p", dmTo]], content }, botSk);
    await Promise.any(pool.publish([RELAY], evt));
    log("DM sent");
  } catch (e) { log("DM failed: " + e.message); }
}

// --- eth JSON-RPC over the same ws ---
let rpcId = 100; const pending = new Map();
let eth;
function call(method, params) {
  return new Promise((resolve, reject) => {
    const id = ++rpcId; pending.set(id, { resolve, reject });
    eth.send(JSON.stringify({ jsonrpc: "2.0", id, method, params }));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error("rpc timeout")); } }, 15000);
  });
}
const toEth = (hex) => Number(BigInt(hex)) / 1e18;

async function snapshot(addr) {
  const [bal, nonce] = await Promise.all([
    call("eth_getBalance", [addr, "latest"]),
    call("eth_getTransactionCount", [addr, "latest"]),
  ]);
  return { eth: toEth(bal), nonce: parseInt(nonce, 16) };
}

const prev = {};

function connect() {
  eth = new WebSocket(ETH_WS, { headers: { "User-Agent": "haskdetect-watcher/0.1 (Hasky Labs)" } });

  eth.on("open", async () => {
    log("connected to " + ETH_WS);
    // baseline
    for (const [k, a] of Object.entries(WATCH)) {
      try { prev[a] = await snapshot(a); log(`baseline ${k}: ${prev[a].eth.toFixed(2)} ETH nonce ${prev[a].nonce}`); } catch {}
    }
    // mempool layer: full pending tx bodies, filter by from/to
    eth.send(JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_subscribe", params: ["newPendingTransactions", true] }));
    // block layer: backstop poll
    setInterval(pollBlocks, POLL);
  });

  eth.on("message", (raw) => {
    let m; try { m = JSON.parse(raw); } catch { return; }
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      return m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result);
    }
    if (m.method === "eth_subscription" && m.params?.result) {
      const tx = m.params.result;
      if (typeof tx !== "object") return; // node sent hash-only; block layer covers it
      const from = tx.from?.toLowerCase(), to = tx.to?.toLowerCase();
      if (SET.has(from) || SET.has(to)) {
        const who = SET.has(from) ? `${nameOf(from)} SENDING` : `-> ${nameOf(to)} RECEIVING`;
        alert(`MEMPOOL: ${who}  tx ${tx.hash}  value ${tx.value ? toEth(tx.value).toFixed(4) : "0"} ETH  (pending, not yet mined)`);
      }
    }
  });

  eth.on("close", () => { log("eth ws closed, reconnecting in 5s"); setTimeout(connect, 5000); });
  eth.on("error", (e) => { log("eth ws error: " + e.message); try { eth.close(); } catch {} });
}

async function pollBlocks() {
  for (const [k, a] of Object.entries(WATCH)) {
    try {
      const cur = await snapshot(a);
      const p = prev[a];
      if (p && (cur.eth !== p.eth || cur.nonce !== p.nonce)) {
        alert(`BLOCK: ${k} moved  ETH ${(cur.eth - p.eth >= 0 ? "+" : "")}${(cur.eth - p.eth).toFixed(4)}  (nonce ${p.nonce}->${cur.nonce})  now ${cur.eth.toFixed(2)} ETH`);
      }
      prev[a] = cur;
    } catch {}
  }
}

log("HaskDetect watcher starting — Case 001");
connect();
