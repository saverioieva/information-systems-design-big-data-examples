import os
import time

from flask import Flask

app = Flask(__name__)

@app.route("/recommendations")
def recommendations():
    time.sleep(float(os.getenv("DELAY_SECONDS", "0")))
    return {"items": ["Pencil"]}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
