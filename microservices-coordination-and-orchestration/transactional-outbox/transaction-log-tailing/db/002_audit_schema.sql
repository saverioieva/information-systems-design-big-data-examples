-- Owned by the Audit Consumer, initialized in postgres_audit only.
CREATE TABLE received_events (
    event_id VARCHAR(40) PRIMARY KEY,
    order_id VARCHAR(40) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
