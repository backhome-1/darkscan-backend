from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 모든 Origin 허용

@app.route("/")
def home():
    return {"status": "ok", "message": "DarkScan backend running"}

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    address = data.get("address", "").strip()

    if not address:
        return jsonify({"error": "No address provided"}), 400

    # --- 여기서 실제 Risk 분석 로직 추가 가능 ---
    # 지금은 더미 데이터 예시
    result = {
        "address": address,
        "status": "risky" if address.startswith("1Boat") else "clean",
        "message": "⚠️ 위험 주소" if address.startswith("1Boat") else "✅ 정상 주소"
    }
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
