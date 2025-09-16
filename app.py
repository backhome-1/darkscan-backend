from flask import Flask, request, jsonify
import os

app = Flask(__name__)

SANCTIONS = {"0x1234abcd5678efgh", "0x9999ffff0000eeee"}

@app.route("/")
def home():
    return jsonify({"message": "DarkScan Backend API is running."})

@app.route("/check")
def check_wallet():
    addr = request.args.get("addr", "").strip()
    if not addr:
        return jsonify({"status": "error", "message": "주소가 없음"})
    if addr in SANCTIONS:
        return jsonify({"status": "risky", "message": "⚠️ 위험 주소"})
    return jsonify({"status": "safe", "message": "🟢 안전 주소"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
