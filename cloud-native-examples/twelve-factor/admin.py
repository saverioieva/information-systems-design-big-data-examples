import os

import redis

client = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379)
value = client.get("hits")
print(f"Current Redis visit count: {int(value) if value else 0}")
