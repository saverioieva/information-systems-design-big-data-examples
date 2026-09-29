import os
import sqlite3

import redis
from flask import Flask, request

app = Flask(__name__)
DB = os.getenv("DB_PATH", "/data/catalog.db")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "30"))
CACHE_INVALIDATION = os.getenv("CACHE_INVALIDATION", "on").lower() not in ("off", "false", "0")
cache = redis.Redis(
    host=os.getenv("REDIS_HOST", "cache"),
    decode_responses=True,
    socket_connect_timeout=0.2,
    socket_timeout=0.2,
)


def init_db():
    with sqlite3.connect(DB) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS products "
            "(id INTEGER PRIMARY KEY, price_cents INTEGER)"
        )
        db.execute("INSERT OR IGNORE INTO products VALUES (1,1200)")


@app.route("/products/1", methods=["GET"])
def get_product():
    try:
        value = cache.get("product:1")
    except redis.RedisError:
        value = None

    if value is not None:
        return {"id": 1, "price_cents": int(value), "source": "cache"}

    with sqlite3.connect(DB) as db:
        value = db.execute(
            "SELECT price_cents FROM products WHERE id=1"
        ).fetchone()[0]

    try:
        cache.setex("product:1", CACHE_TTL_SECONDS, value)
    except redis.RedisError:
        pass

    return {"id": 1, "price_cents": value, "source": "database"}


@app.route("/products/1", methods=["PUT"])
def update_product():
    data = request.get_json(silent=True) or {}
    value = data.get("price_cents")

    if type(value) is not int or value < 0:
        return {"error": "price_cents must be a non-negative integer"}, 400

    with sqlite3.connect(DB) as db:
        db.execute("UPDATE products SET price_cents=? WHERE id=1", (value,))

    invalidated = False
    if CACHE_INVALIDATION:
        try:
            cache.delete("product:1")
            invalidated = True
        except redis.RedisError:
            pass

    return {
        "saved": True,
        "cache_invalidation_enabled": CACHE_INVALIDATION,
        "cache_invalidated": invalidated,
    }


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
