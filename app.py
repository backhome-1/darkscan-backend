
import os
import json
import csv
from datetime import datetime, timezone
from typing import Dict, List, Set, Tuple, Optional
import requests
from flask import Flask, request, jsonify, abort
from flask_cors import CORS

# -----------------------------
# Config (ENV)
# -----------------------------
PORT = int(os.environ.get("PORT", "10000"))
CACHE_FILE = os.environ.get("CACHE_FILE", "/tmp/sanctions_cache.json")
# Comma-separated list of HTTP(S) URLs to JSON/CSV sources
SANCTIONS_URLS_ENV = os.environ.get("SANCTIONS_URLS", "")
# Optional Bearer token for admin refresh endpoint
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
# CORS origins (comma separated). Default "*" for MVP with HF Static.
ALLOW_ORIGINS = [o.strip() for o in os.environ.get("ALLOW_ORIGINS", "*").split(",") if o.strip()]

# Reasonable defaults if env not provided (replace with your org's curated aggregator)
DEFAULT_URLS = [
    # JSON examples (replace with your real sources)
    # Each should provide addresses either as a list of strings, a dict of {address: meta},
    # or a list of dicts with an "address" field.
    "https://example.com/sanctions/latest.json",
    # CSV examples (must include a column named address OR wallet)
    "https://example.com/sanctions/crypto_addresses.csv"
]

SANCTIONS_URLS: List[str] = [u for u in (SANCTIONS_URLS_ENV.split(",") if SANCTIONS_URLS_ENV else DEFAULT_URLS) if u]

# -----------------------------
# App & CORS
# -----------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ALLOW_ORIGINS}})

# -----------------------------
# Storage
# -----------------------------
# addr -> set(sources)
SANCTIONS_INDEX: Dict[str, Set[str]] = {}
LAST_UPDATE: Optional[str] = None  # ISO timestamp
SOURCES_USED: List[str] = []

# -----------------------------
# Chain heuristics (non-blocking)
# -----------------------------
def detect_chain(addr: str) -> str:
    a = addr.strip()
    if a.startswith("0x") and 40 <= len(a[2:]) <= 64:
        return "ethereum_like"  # ETH, BSC, etc (heuristic)
    if a.startswith("bc1") or a.startswith("1") or a.startswith("3"):
        return "bitcoin_like"
    if a.startswith("tb1"):
        return "bitcoin_testnet"
    if a.startswith("T") and 30 <= len(a) <= 45:
        return "tron_like"
    if a.startswith("L") and 26 <= len(a) <= 35:
        return "litecoin_like"
    if a.startswith("D") and 26 <= len(a) <= 35:
        return "dogecoin_like"
    if a.startswith("r") and 25 <= len(a) <= 35:
        return "xrp_like"
    if len(a) in (32, 44) and all(c.isalnum() for c in a):
        return "solana_like"
    return "unknown"

# -----------------------------
# Fetch/parsing helpers
# -----------------------------
def _normalize_address(s: str) -> str:
    return s.strip()

def _add_addr(addr: str, source: str):
    addr_n = _normalize_address(addr)
    if not addr_n:
        return
    SANCTIONS_INDEX.setdefault(addr_n, set()).add(source)

def parse_json_payload(payload, source: str):
    # Accept: list[str], list[dict], dict[str, ...], dict[key -> list[str]]
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                _add_addr(item, source)
            elif isinstance(item, dict):
                # common fields
                for key in ("address", "addr", "wallet", "wallet_address"):
                    if key in item and isinstance(item[key], str):
                        _add_addr(item[key], source)
    elif isinstance(payload, dict):
        # If dict of addresses
        for k, v in payload.items():
            if isinstance(k, str) and (isinstance(v, (dict, list, str, int, float, bool))):
                # key looks like an address
                if any(c.isalnum() for c in k):
                    _add_addr(k, source)
            # Or known lists under a key
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, str):
                        _add_addr(x, source)
                    elif isinstance(x, dict):
                        for key in ("address", "addr", "wallet", "wallet_address"):
                            if key in x and isinstance(x[key], str):
                                _add_addr(x[key], source)

def parse_csv_text(text: str, source: str):
    reader = csv.DictReader(text.splitlines())
    cols = [c.lower() for c in reader.fieldnames or []]
    addr_col = None
    for cand in ("address", "wallet", "wallet_address", "addr"):
        if cand in cols:
            addr_col = cand
            break
    if not addr_col:
        # Fallback: first column
        addr_col = cols[0] if cols else None
    if not addr_col:
        return
    for row in reader:
        val = None
        for k, v in row.items():
            if k.lower() == addr_col:
                val = v
                break
        if isinstance(val, str):
            _add_addr(val, source)

def fetch_all_sources(urls: List[str]) -> Tuple[int, List[str]]:
    fetched = 0
    used = []
    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            ct = (r.headers.get("content-type") or "").lower()
            if r.status_code != 200:
                continue
            if "application/json" in ct or r.text.strip().startswith(("{", "[")):
                data = r.json()
                parse_json_payload(data, url)
                fetched += 1
                used.append(url)
            elif "text/csv" in ct or "," in r.text[:200]:
                parse_csv_text(r.text, url)
                fetched += 1
                used.append(url)
            else:
                # Try json anyway
                try:
                    data = r.json()
                    parse_json_payload(data, url)
                    fetched += 1
                    used.append(url)
                except Exception:
                    # Ignore unknown format
                    pass
        except Exception as e:
            # Log and continue
            print(f"[WARN] fetch failed for {url}: {e}")
    return fetched, used

def persist_cache():
    try:
        blob = {
            "last_update": LAST_UPDATE,
            "count": len(SANCTIONS_INDEX),
            "sources": list(SOURCES_USED),
            "addresses": list(SANCTIONS_INDEX.keys()),
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(blob, f, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] cache persist failed: {e}")

def load_cache_if_exists() -> bool:
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                blob = json.load(f)
            addrs = blob.get("addresses", [])
            for a in addrs:
                _add_addr(a, "cache")
            return True
    except Exception as e:
        print(f"[WARN] cache load failed: {e}")
    return False

def bootstrap():
    global LAST_UPDATE, SOURCES_USED
    SANCTIONS_INDEX.clear()
    fetched, used = fetch_all_sources(SANCTIONS_URLS)
    if fetched == 0:
        # Fallback to cache
        ok = load_cache_if_exists()
        LAST_UPDATE = datetime.now(timezone.utc).isoformat()
        SOURCES_USED = ["cache"] if ok else []
        print(f"[INFO] bootstrap via CACHE ok={ok} count={len(SANCTIONS_INDEX)}")
    else:
        LAST_UPDATE = datetime.now(timezone.utc).isoformat()
        SOURCES_USED = used
        persist_cache()
        print(f"[INFO] bootstrap fetched={fetched} sources={len(used)} addrs={len(SANCTIONS_INDEX)}")

# -----------------------------
# API
# -----------------------------
@app.get("/")
def root():
    return jsonify({
        "message": "DarkScan Backend API is running.",
        "count": len(SANCTIONS_INDEX),
        "last_update": LAST_UPDATE,
        "sources": SOURCES_USED
    })

@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "count": len(SANCTIONS_INDEX),
        "last_update": LAST_UPDATE,
    })

@app.get("/check")
def check():
    addr = (request.args.get("addr") or "").strip()
    if not addr:
        return jsonify({"status": "error", "message": "❌ 주소를 입력하세요"}), 400

    matched_sources = list(SANCTIONS_INDEX.get(addr, []))
    status = "risky" if matched_sources else "safe"
    message = "⚠️ 위험 주소" if matched_sources else "🟢 안전 주소"

    return jsonify({
        "status": status,
        "message": message,
        "address": addr,
        "detected_chain": detect_chain(addr),
        "matched_sources": matched_sources,
        "count": len(SANCTIONS_INDEX),
        "last_update": LAST_UPDATE
    })

@app.post("/admin/refresh")
def admin_refresh():
    # Optional bearer token check
    if ADMIN_TOKEN:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth.split(" ", 1)[1] != ADMIN_TOKEN:
            abort(401)
    # Refresh data
    bootstrap()
    return jsonify({
        "status": "refreshed",
        "count": len(SANCTIONS_INDEX),
        "last_update": LAST_UPDATE,
        "sources": SOURCES_USED
    })

# -----------------------------
# Boot
# -----------------------------
bootstrap()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

