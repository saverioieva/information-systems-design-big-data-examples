from flask import Flask
import os
import socket

app = Flask(__name__)
VERSION = os.getenv("APP_VERSION", "v1")

@app.get("/")
def home():
    return f"Hello from {VERSION} | host={socket.gethostname()}\n"

@app.get("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    # Flask dev server is enough for demo purposes
    app.run(host="0.0.0.0", port=5000)
