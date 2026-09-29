import json
import os
import time
import urllib.request

from flask import Flask

app = Flask(__name__)
URL = os.getenv("RECOMMENDATIONS_URL", "http://recommendations:5000")
FRAGILE_TIMEOUT = float(os.getenv("FRAGILE_TIMEOUT_SECONDS", "5"))
RESILIENT_TIMEOUT = float(os.getenv("RESILIENT_TIMEOUT_SECONDS", "0.3"))


def fetch(timeout):
    with urllib.request.urlopen(URL + "/recommendations", timeout=timeout) as response:
        return json.load(response)["items"]


@app.route("/catalog/<mode>")
def catalog(mode):
    if mode not in ("fragile", "resilient"):
        return {"error": "use fragile or resilient"}, 404

    started = time.monotonic()
    timeout = RESILIENT_TIMEOUT if mode == "resilient" else FRAGILE_TIMEOUT

    try:
        items = fetch(timeout)
        degraded = False
    except (OSError, ValueError):
        if mode == "fragile":
            return {"error": "dependency unavailable"}, 503
        items = []
        degraded = True

    return {
        "product": "Notebook",
        "recommendations": items,
        "degraded": degraded,
        "timeout_seconds": timeout,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
    }


@app.route("/livez")
def live():
    return {"alive": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
