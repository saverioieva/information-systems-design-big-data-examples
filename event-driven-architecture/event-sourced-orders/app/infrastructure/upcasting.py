"""A standalone demonstration of upcasting a historical event payload.

This function is NOT installed in the eventsourcing library's mapper. It is
included as an explicit classroom example of what an upcaster does, rather
than falsely implying that live event reads are automatically migrated.
"""
from typing import Any, Dict

def upcast_order_event_state(state: Dict[str, Any]) -> Dict[str, Any]:
    version = int(state.get("event_schema_version", 1))
    result = dict(state)
    if version == 1:
        # Schema v2 introduces an explicit sales channel field.
        result.setdefault("sales_channel", "UNKNOWN")
        result["event_schema_version"] = 2
        return result
    if version == 2:
        return result
    raise ValueError(f"Unsupported event schema version: {version}")
