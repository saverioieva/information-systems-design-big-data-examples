from flask import Flask

app = Flask(__name__)

@app.route("/products/1")
def product():
    return {"id": 1, "price_cents": 1200}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
