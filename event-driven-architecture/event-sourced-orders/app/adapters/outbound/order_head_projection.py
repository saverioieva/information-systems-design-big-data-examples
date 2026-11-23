import os
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from app.domain.models import Order


class OrderHeadProjector:
    """Projection into a simple SQL table that acts like an aggregate-root table.

    Schema:

        order_head(
          order_id UUID PRIMARY KEY,
          current_version INT NOT NULL,
          aggregate_schema_version INT NOT NULL,
          state_version INT NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL
        )
    """

    def __init__(self) -> None:
        self._dsn = self._build_dsn()

    def _build_dsn(self) -> str:
        host = os.getenv("POSTGRES_HOST", "db")
        port = os.getenv("POSTGRES_PORT", "5432")
        dbname = os.getenv("POSTGRES_DBNAME", "orders_es")
        user = os.getenv("POSTGRES_USER", "eventsourcing")
        password = os.getenv("POSTGRES_PASSWORD", "eventsourcing")
        return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    def _get_conn(self):
        return psycopg.connect(self._dsn, row_factory=dict_row)

    def ensure_schema(self) -> None:
        ddl = '''
        CREATE TABLE IF NOT EXISTS order_head (
          order_id UUID PRIMARY KEY,
          current_version INT NOT NULL,
          aggregate_schema_version INT NOT NULL,
          state_version INT NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL
        );
        '''
        with self._get_conn() as conn, conn.cursor() as cur:
            cur.execute(ddl)
            conn.commit()

    def project_order(self, order: Order) -> None:
        """Upserts the current aggregate head row for the given order."""

        sql = '''
        INSERT INTO order_head (order_id, current_version, aggregate_schema_version, state_version, updated_at)
        VALUES (%(order_id)s, %(current_version)s, %(aggregate_schema_version)s, %(state_version)s, %(updated_at)s)
        ON CONFLICT (order_id)
        DO UPDATE SET
          current_version = EXCLUDED.current_version,
          aggregate_schema_version = EXCLUDED.aggregate_schema_version,
          state_version = EXCLUDED.state_version,
          updated_at = EXCLUDED.updated_at;
        '''
        params = {
            "order_id": str(order.id),
            "current_version": int(order.version),
            "aggregate_schema_version": int(order.aggregate_schema_version),
            "state_version": int(order.state_version or order.version),
            "updated_at": datetime.utcnow(),
        }

        with self._get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
