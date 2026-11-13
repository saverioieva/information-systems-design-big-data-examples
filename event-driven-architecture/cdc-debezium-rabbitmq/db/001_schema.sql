-- This database owns current Order state. Both publications exist before the connector starts.
CREATE TABLE orders (
    id VARCHAR(40) PRIMARY KEY,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    status VARCHAR(40) NOT NULL CHECK (status IN ('CREATED', 'APPROVED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE outbox_events (
    event_id VARCHAR(40) PRIMARY KEY,
    aggregate_type VARCHAR(80) NOT NULL,
    aggregate_id VARCHAR(40) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Separate publications and slots to isolate RAW row changes from integration contracts.
CREATE PUBLICATION raw_orders_publication FOR TABLE public.orders;
CREATE PUBLICATION integration_outbox_publication FOR TABLE public.outbox_events;
