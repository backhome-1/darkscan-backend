from flask import Flask, request, jsonify

app = Flask(__name__)

# 임시 제재 리스트 (나중에 sanctions.json으로 교체 가능)
SANCTIONS = {"0x1234abcd5678efgh", "0x9999ffff0000eeee"}

@app.route("/check")
def check_wallet():
    addr = request.args.get("addr", "").strip()
    if not addr:
        return jsonify({"status": "error", "message": "주소가 없음"})

    if addr in SANCTIONS:
        return jsonify({"status": "risky", "message": "⚠️ 위험 주소"})
    else:
        return jsonify({"status": "safe", "message": "🟢 안전 주소"})

if __name__ == "__main__":
    # Render는 PORT 환경변수를 씀 → 없으면 5000번
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
