import requests
import csv
from flask import Flask, request, jsonify
from flask_cors import CORS

# Flask 앱 생성
app = Flask(__name__)
CORS(app)  # 브라우저 호출 허용

# 데이터 소스 (항상 최신 유지됨)
OFAC_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
OPEN_SANCTIONS_URL = "https://api.opensanctions.org/match/"

# OFAC 제재 리스트 체크 함수
def check_ofac(address: str) -> bool:
    try:
        res = requests.get(OFAC_URL, timeout=10)
        res.raise_for_status()
        lines = res.text.splitlines()
        reader = csv.reader(lines)
        for row in reader:
            if address in row:
                return True
    except Exception as e:
        print("OFAC fetch error:", e)
    return False

@app.route("/")
def home():
    """헬스체크 엔드포인트"""
    return {"status": "ok", "message": "DarkScan backend running"}

@app.route("/analyze", methods=["POST"])
def analyze():
    """암호화폐 지갑 주소 위험도 분석"""
    data = request.get_json()
    address = data.get("address", "").strip()

    if not address:
        return jsonify({"error": "No address provided"}), 400

    # 1) OFAC 리스트 확인
    if check_ofac(address):
        return jsonify({
            "address": address,
            "status": "risky",
            "source": "OFAC",
            "message": "⚠️ OFAC 제재 명단에 포함"
        })

    # 2) OpenSanctions API 확인
    try:
        payload = {"query": address}
        res = requests.post(OPEN_SANCTIONS_URL, json=payload, timeout=10)
        res.raise_for_status()
        result = res.json()
        if result.get("matches"):
            return jsonify({
                "address": address,
                "status": "risky",
                "source": "OpenSanctions",
                "message": "⚠️ OpenSanctions DB에 포함",
                "details": result["matches"]
            })
    except Exception as e:
        return jsonify({"error": f"OpenSanctions lookup failed: {str(e)}"}), 500

    # 3) 기본 clean 처리
    return jsonify({
        "address": address,
        "status": "clean",
        "message": "✅ 제재 DB에 없음"
    })

# Render에서 실행될 때 진입점
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
