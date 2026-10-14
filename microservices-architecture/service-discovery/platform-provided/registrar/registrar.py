import os
import time
from dataclasses import dataclass

import docker
import requests

CONSUL_HTTP_ADDR = os.getenv("CONSUL_HTTP_ADDR", "http://consul:8500")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2"))


@dataclass(frozen=True)
class Registration:
    service_id: str
    name: str
    instance: str
    address: str
    port: int


def container_ip(container) -> str | None:
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
    for network in networks.values():
        address = network.get("IPAddress")
        if address:
            return address
    return None


def registration_for(container) -> Registration | None:
    labels = container.labels or {}
    if labels.get("discovery.enabled", "false").lower() != "true":
        return None

    name = labels.get("discovery.name")
    instance = labels.get("discovery.instance", container.short_id)
    port = labels.get("discovery.port")
    address = container_ip(container)

    if not name or not port or not address:
        return None

    return Registration(
        service_id=f"{name}-{instance}",
        name=name,
        instance=instance,
        address=address,
        port=int(port),
    )


def wait_for_consul() -> None:
    for _ in range(30):
        try:
            requests.get(f"{CONSUL_HTTP_ADDR}/v1/status/leader", timeout=2).raise_for_status()
            return
        except requests.RequestException:
            time.sleep(1)
    raise RuntimeError("Consul did not become ready")


def register(registration: Registration) -> None:
    payload = {
        "ID": registration.service_id,
        "Name": registration.name,
        "Address": registration.address,
        "Port": registration.port,
        "Meta": {
            "instance": registration.instance,
            "registration": "third-party",
        },
        "Check": {
            "HTTP": f"http://{registration.address}:{registration.port}/health",
            "Interval": "3s",
            "Timeout": "1s",
            "DeregisterCriticalServiceAfter": "30s",
        },
    }
    response = requests.put(
        f"{CONSUL_HTTP_ADDR}/v1/agent/service/register",
        json=payload,
        timeout=3,
    )
    response.raise_for_status()


def deregister(service_id: str) -> None:
    requests.put(
        f"{CONSUL_HTTP_ADDR}/v1/agent/service/deregister/{service_id}",
        timeout=3,
    ).raise_for_status()


def main() -> None:
    wait_for_consul()
    client = docker.from_env()
    known: dict[str, Registration] = {}

    print("Third-party registrar started", flush=True)
    print("Watching Docker containers labelled discovery.enabled=true", flush=True)

    while True:
        containers = client.containers.list(filters={"label": "discovery.enabled=true"})
        current: dict[str, Registration] = {}

        for container in containers:
            container.reload()
            registration = registration_for(container)
            if registration:
                current[registration.service_id] = registration

        for service_id, registration in current.items():
            if known.get(service_id) != registration:
                register(registration)
                print(
                    f"[register] {service_id} -> "
                    f"{registration.address}:{registration.port}",
                    flush=True,
                )

        for service_id in sorted(set(known) - set(current)):
            try:
                deregister(service_id)
                print(f"[deregister] {service_id}", flush=True)
            except requests.RequestException as exc:
                print(f"[deregister] {service_id} failed: {exc}", flush=True)

        known = current
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
