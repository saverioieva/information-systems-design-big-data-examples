import logging
import os

import redis
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
r = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379)
MESSAGE = os.getenv("APP_MESSAGE", "Hello")
APP_ENV = os.getenv("APP_ENV", "development")

@app.route("/")
def index():
    count = r.incr("hits")
    logger.info("request served environment=%s visit=%s", APP_ENV, count)
    return (
        f"<h1>{MESSAGE}</h1>"
        f"<p>Environment: {APP_ENV}</p>"
        f"<p>Visit stored in Redis: {count}</p>"
    )

@app.route("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
