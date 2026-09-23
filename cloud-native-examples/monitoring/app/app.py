from flask import Flask, request
from prometheus_client import Counter, Histogram, generate_latest
import random
import time

app = Flask(__name__)

REQUEST_COUNT = Counter('flask_http_request_total', 'Total HTTP Requests', ['method', 'endpoint', 'http_status'])
REQUEST_LATENCY = Histogram('flask_http_request_duration_seconds', 'Request latency')

@app.route('/')
def index():
    start = time.time()
    number = random.randint(1, 100)
    time.sleep(random.random())
    status = 200
    REQUEST_COUNT.labels(method=request.method, endpoint="/", http_status=status).inc()
    REQUEST_LATENCY.observe(time.time() - start)
    app.logger.info(f"Request served with number={number}")
    return f"<h1>Hello!</h1><p>Random number: {number}</p>"

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
