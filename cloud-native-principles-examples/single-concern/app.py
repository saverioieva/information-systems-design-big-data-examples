from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify


app = Flask(__name__)
CONFIG_FILE = Path("/config/message.txt")
LOG_FILE = Path("/logs/access.log")


def read_message():
    return CONFIG_FILE.read_text().strip()


def write_access_log():
    timestamp = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a") as log_file:
        log_file.write(f"{timestamp} GET /catalog\n")
        log_file.flush()


@app.get("/catalog")
def catalog():
    write_access_log()
    return jsonify(
        service="catalog",
        message=read_message(),
        products=["notebook", "keyboard", "mouse"],
    )


@app.get("/livez")
def livez():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
