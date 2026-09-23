from flask import Flask
import os

app = Flask(__name__)
VERSION = os.getenv("VERSION", "v1")

@app.route("/")
def index():
    return f"<h1>Hello from version {VERSION}</h1>"

@app.route("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
