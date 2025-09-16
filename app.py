from flask import Flask, request, jsonify
import re
import base58
import csv

app = Flask(__name__)

# ---- CSV 로딩 ----
def load_sanctions():
    sanctioned = set()
    with open("ofac_sdn.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = row.get("Address", "").strip()
            if addr:
                sanctioned.add(addr)
    return sanctioned

SANCTIONED_ADDRESSES = load_sanctions()

# ---- BTC 검증 ----
def is_valid_btc_address(address: str) -> bool:
    if not re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$', address):
        return False
    try:
        decoded = base58.b58decode_check(address)
        return len(decoded) in [21]
    except Exception:
        return False

@app.route("/check", methods=["POST"])
def check_address():
    data = request.get_json()
    address = data.get("address", "").strip()

    if not address:
        return jsonify({"message": "❌ 주소 없음", "status": "invalid"}), 400

    if not is_valid_btc_address(address):
        return jsonify({"message": "❌ 유효하지 않은 비트코인 주소", "status": "invalid"}), 200

    if address in SANCTIONED_ADDRESSES:
        return jsonify({"message": "⚠️ 위험 주소 (제재 리스트 일치)", "status": "risky"}), 200

    return jsonify({"message": "✅ 정상 주소 (제재 리스트에 없음)", "status": "safe"}), 200

@app.route("/", methods=["GET"])
def home():
    return "DarkScan API v5 - Free Sanction Checker"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
