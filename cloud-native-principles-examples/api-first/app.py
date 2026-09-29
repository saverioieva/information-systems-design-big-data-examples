import os

from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/products/1")
def product():
    mode = os.getenv("API_MODE", "v1")
    data = {"id": 1, "name": "Notebook", "price_cents": 1200}

    if mode == "additive":
        data["currency"] = "EUR"
        data["price_euros"] = data["price_cents"] / 100
    elif mode == "breaking":
        data["price"] = data.pop("price_cents") / 100

    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
