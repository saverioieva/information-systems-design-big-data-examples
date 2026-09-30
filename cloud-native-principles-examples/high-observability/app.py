import json
import logging
import os
import random
import time
import urllib.request
import uuid

from flask import Flask, request
from prometheus_client import Counter, Gauge, Histogram, generate_latest

app = Flask(__name__)
STARTED_AT = time.monotonic()
READY = True
JAEGER_ZIPKIN_ENDPOINT = os.getenv(
    "JAEGER_ZIPKIN_ENDPOINT",
    "http://jaeger:9411/api/v2/spans",
)

REQUEST_COUNT = Counter(
    "observability_http_requests",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "observability_http_request_duration_seconds",
    "HTTP request duration",
    ["endpoint"],
)
READINESS = Gauge(
    "observability_readiness",
    "Application readiness: 1 when ready, 0 when not ready",
)
READINESS.set(1)

logger = logging.getLogger("observability-demo")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.handlers.clear()
logger.addHandler(handler)
logger.propagate = False


def structured_log(**fields):
    logger.info(json.dumps(fields, separators=(",", ":")))


def export_span(trace_id, span_id, started_us, duration_us, status_code):
    span = [{
        "traceId": trace_id,
        "id": span_id,
        "name": "GET /catalog",
        "timestamp": started_us,
        "duration": duration_us,
        "localEndpoint": {"serviceName": "catalog-service"},
        "tags": {
            "http.method": "GET",
            "http.route": "/catalog",
            "http.status_code": str(status_code),
        },
    }]

    data = json.dumps(span).encode("utf-8")
    req = urllib.request.Request(
        JAEGER_ZIPKIN_ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        urllib.request.urlopen(req, timeout=0.2).read()
    except OSError:
        structured_log(event="trace_export_failed", trace_id=trace_id)


@app.route("/catalog")
def catalog():
    started = time.monotonic()
    started_us = int(time.time() * 1_000_000)
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    trace_id = request.headers.get("X-Trace-ID", uuid.uuid4().hex)
    span_id = uuid.uuid4().hex[:16]

    delay = round(random.uniform(0.05, 0.30), 2)
    time.sleep(delay)

    status = 500 if request.args.get("fail") == "1" else 200
    duration = time.monotonic() - started

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint="/catalog",
        status=str(status),
    ).inc()
    REQUEST_LATENCY.labels(endpoint="/catalog").observe(duration)

    structured_log(
        event="request_completed",
        request_id=request_id,
        trace_id=trace_id,
        method=request.method,
        path=request.path,
        status=status,
        duration_ms=round(duration * 1000, 1),
    )

    export_span(
        trace_id=trace_id,
        span_id=span_id,
        started_us=started_us,
        duration_us=int(duration * 1_000_000),
        status_code=status,
    )

    body = {
        "product": "Notebook",
        "price_cents": 1200,
        "request_id": request_id,
        "trace_id": trace_id,
    }
    headers = {
        "X-Request-ID": request_id,
        "X-Trace-ID": trace_id,
    }
    return body, status, headers


@app.route("/livez")
def livez():
    return {
        "status": "alive",
        "pid": os.getpid(),
        "uptime_seconds": round(time.monotonic() - STARTED_AT, 1),
    }


@app.route("/readyz")
def readyz():
    if READY:
        return {"status": "ready"}
    return {"status": "not-ready"}, 503


@app.route("/admin/readiness/<state>", methods=["POST"])
def set_readiness(state):
    global READY

    if state == "ready":
        READY = True
        READINESS.set(1)
    elif state == "not-ready":
        READY = False
        READINESS.set(0)
    else:
        return {"error": "use ready or not-ready"}, 400

    structured_log(event="readiness_changed", ready=READY)
    return {"ready": READY}


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
