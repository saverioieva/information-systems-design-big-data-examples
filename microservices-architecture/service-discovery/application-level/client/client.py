import os
import time
from dataclasses import dataclass

import requests

CONSUL_HTTP_ADDR = os.getenv("CONSUL_HTTP_ADDR", "http://consul:8500")
SERVICE_NAME = os.getenv("SERVICE_NAME", "order-service")
ORDER_ID = os.getenv("ORDER_ID", "1001")
REQUEST_COUNT = int(os.getenv("REQUEST_COUNT", "9"))


@dataclass(frozen=True)
class Instance:
    service_id: str
    address: str
    port: int
    name: str

    @property
    def base_url(self) -> str:
        return f"http://{self.address}:{self.port}"


def discover_instances() -> list[Instance]:
    response = requests.get(
        f"{CONSUL_HTTP_ADDR}/v1/health/service/{SERVICE_NAME}",
        params={"passing": "true"},
        timeout=3,
    )
    response.raise_for_status()

    instances = []
    for item in response.json():
        service = item["Service"]
        address = service.get("Address") or item["Node"].get("Address")
        port = service.get("Port")
        if address and port:
            instances.append(
                Instance(
                    service_id=service["ID"],
                    address=address,
                    port=int(port),
                    name=service.get("Meta", {}).get("instance", service["ID"]),
                )
            )

    instances.sort(key=lambda instance: instance.service_id)
    return instances


def wait_for_instances(minimum: int = 1) -> list[Instance]:
    last_error = None
    for _ in range(30):
        try:
            instances = discover_instances()
            if len(instances) >= minimum:
                return instances
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(1)

    if last_error:
        raise RuntimeError(f"Consul did not become ready: {last_error}")
    raise RuntimeError(f"No healthy instances found for {SERVICE_NAME}")


def print_membership(instances: list[Instance]) -> None:
    print(f"\nDiscovered {len(instances)} healthy instance(s) for '{SERVICE_NAME}':")
    for instance in instances:
        print(f"  - {instance.name:<8} {instance.address}:{instance.port}")


def main() -> None:
    wait_for_instances()
    previous_ids: tuple[str, ...] = ()
    cursor = 0

    print("Application-level discovery demo")
    print("Client queries Consul and selects the target instance itself.\n")

    for request_number in range(1, REQUEST_COUNT + 1):
        instances = wait_for_instances()
        current_ids = tuple(instance.service_id for instance in instances)
        if current_ids != previous_ids:
            print_membership(instances)
            previous_ids = current_ids
            cursor = 0

        target = instances[cursor % len(instances)]
        cursor += 1

        try:
            response = requests.get(
                f"{target.base_url}/orders/{ORDER_ID}",
                timeout=2,
            )
            response.raise_for_status()
            body = response.json()
            print(
                f"{request_number:02d}. selected {target.name:<8} -> "
                f"HTTP {response.status_code}, response instance={body['instance']}"
            )
        except requests.RequestException as exc:
            print(f"{request_number:02d}. selected {target.name:<8} -> ERROR {exc}")

        time.sleep(0.4)


if __name__ == "__main__":
    main()
