from app.infrastructure.upcasting import upcast_order_event_state

def test_v1_is_upcast_to_v2_without_mutating_history():
    old={"event_schema_version": 1, "event_type": "OrderCreated"}
    new=upcast_order_event_state(old)
    assert new["sales_channel"]=="UNKNOWN"
    assert new["event_schema_version"]==2
    assert "sales_channel" not in old

def test_v2_is_unchanged():
    event={"event_schema_version":2,"sales_channel":"WEB"}
    assert upcast_order_event_state(event)==event
