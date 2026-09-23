from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle():
    name = request.data.decode("utf-8") or "World"
    return f"Hello {name}, from the Function!"

@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200
