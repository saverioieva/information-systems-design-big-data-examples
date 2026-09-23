from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello from the PaaS demo! You just wrote your code, the platform runs it."

@app.route("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
