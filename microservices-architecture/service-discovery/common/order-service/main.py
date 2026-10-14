import os
import socket
import time
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI

SERVICE_NAME = os.getenv("SERVICE_NAME", "order-service")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", socket.gethostname())
SELF_REGISTER = os.getenv("SELF_REGISTER", "false").lower() == "true"
CONSUL_HTTP_ADDR = os.getenv("CONSUL_HTTP_ADDR", "http://consul:8500")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8000"))


def instance_ip() -> str:
    return socket.gethostbyname(socket.gethostname())


def service_id() -> str:
    return f"{SERVICE_NAME}-{INSTANCE_NAME}"


def register_with_consul() -> None:
    address = instance_ip()
    payload = {
        "ID": service_id(),
        "Name": SERVICE_NAME,
        "Address": address,
        "Port": SERVICE_PORT,
        "Meta": {"instance": INSTANCE_NAME, "registration": "self"},
        "Check": {
            "HTTP": f"http://{address}:{SERVICE_PORT}/health",
            "Interval": "3s",
            "Timeout": "1s",
            "DeregisterCriticalServiceAfter": "30s",
        },
    }

    last_error = None
    for _ in range(30):
        try:
            response = requests.put(
                f"{CONSUL_HTTP_ADDR}/v1/agent/service/register",
                json=payload,
                timeout=2,
            )
            response.raise_for_status()
            print(
                f"[self-registration] {service_id()} -> {address}:{SERVICE_PORT}",
                flush=True,
            )
            return
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(1)

    raise RuntimeError(f"Unable to register with Consul: {last_error}")


def deregister_from_consul() -> None:
    try:
        requests.put(
            f"{CONSUL_HTTP_ADDR}/v1/agent/service/deregister/{service_id()}",
            timeout=2,
        ).raise_for_status()
        print(f"[self-registration] deregistered {service_id()}", flush=True)
    except requests.RequestException as exc:
        print(f"[self-registration] deregistration failed: {exc}", flush=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if SELF_REGISTER:
        register_with_consul()
    yield
    if SELF_REGISTER:
        deregister_from_consul()


app = FastAPI(title=f"Order Service - {INSTANCE_NAME}", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "instance": INSTANCE_NAME}


@app.get("/orders/{order_id}")
def get_order(order_id: str) -> dict:
    return {
        "orderId": order_id,
        "status": "CONFIRMED",
        "total": 42.50,
        "instance": INSTANCE_NAME,
        "containerHost": socket.gethostname(),
    }
