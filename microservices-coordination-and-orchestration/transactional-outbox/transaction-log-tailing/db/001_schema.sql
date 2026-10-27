-- Business state is persisted in orders, NOT reconstructed from messages.
-- The outbox row is committed atomically with the order state.
CREATE TABLE orders (
    id VARCHAR(40) PRIMARY KEY,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    status VARCHAR(30) NOT NULL
);
CREATE TABLE outbox_events (
    event_id VARCHAR(40) PRIMARY KEY,
    aggregate_type VARCHAR(80) NOT NULL,
    aggregate_id VARCHAR(40) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Teaching-only consumer deduplication table.
CREATE TABLE received_events (
    event_id VARCHAR(40) PRIMARY KEY,
    order_id VARCHAR(40) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- wal2json reads the WAL through a logical slot; no SQL publication required.
