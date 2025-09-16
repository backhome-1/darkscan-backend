from flask import Flask, request, Response
from flask_cors import CORS
import json
import os

app = Flask(__name__)

# 🔓 CORS 완전 허용
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True,
    allow_headers="*",
    methods=["GET", "POST", "OPTIONS"]
)

@app.route("/", methods=["GET"])
def home():
    return Response(
        json.dumps({"message": "DarkScan Backend API is running."}, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )

@app.route("/check", methods=["GET"])
def check_wallet():
    addr = request.args.get("addr", "").strip()

    if not addr:
        return Response(
            json.dumps({"message": "❌ 주소를 입력하세요", "status": "error"}, ensure_ascii=False),
            content_type="application/json; charset=utf-8",
            status=400
        )

    # 🚨 샘플 제재 리스트 (실제로는 DB/실시간 API 연동 가능)
    blacklist = {
        "0x1234abcd5678efgh",  # ETH
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7k3l9y0r",  # BTC
        "TXYZ1234567890ABCDE"  # TRON
    }

    if addr in blacklist:
        return Response(
            json.dumps({
                "message": "⚠️ 위험 주소",
                "status": "risky",
                "detected_chain": "auto-detect"
            }, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

    return Response(
        json.dumps({
            "message": "🟢 안전 주소",
            "status": "safe",
            "detected_chain": "auto-detect"
        }, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
