"""External coupling: modules depend on the same externally imposed format/protocol."""


EXTERNAL_PACKET_SEPARATOR = "|"


class SensorModule:
    def temperature(self, packet: str) -> float:
        kind, value = packet.split(EXTERNAL_PACKET_SEPARATOR)
        if kind != "TEMP":
            raise ValueError("unexpected device packet")
        return float(value)


class AuditModule:
    def describe(self, packet: str) -> str:
        # This module must understand the same external device packet format.
        kind, value = packet.split(EXTERNAL_PACKET_SEPARATOR)
        return f"device-packet kind={kind} value={value}"


def demo() -> list[str]:
    packet = "TEMP|22.5"  # format imposed by an external device/protocol
    return [
        f"temperature={SensorModule().temperature(packet):.1f}",
        AuditModule().describe(packet),
        "Observe: both modules are coupled to the same external packet format.",
    ]
