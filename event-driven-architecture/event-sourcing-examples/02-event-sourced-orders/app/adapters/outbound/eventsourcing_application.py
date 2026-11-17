from __future__ import annotations

from typing import List, Dict, Any, ClassVar, Type, Optional
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import IntegrityError, JSONTranscoder

from app.domain.models import Order
from app.adapters.outbound.order_head_projection import OrderHeadProjector
from app.adapters.outbound.transcoding import OrderLineItemAsDict


from app.application.errors import ConcurrencyError


class OrderApplication(Application):
    """Application service for the Order aggregate.

    Responsibilities:
    - event-sourced persistence using the eventsourcing library,
    - snapshotting for fast rebuilds of large aggregates,
    - optimistic locking using the aggregate version,
    - projection into a relational aggregate-head table (order_head),
    - registration of custom transcodings for snapshots (OrderLineItem).
    """

    # Enable snapshotting.
    is_snapshotting_enabled = True

    # Take a snapshot every 2 events to make the demo easy to observe.
    snapshotting_intervals: ClassVar[dict[Type[Aggregate], int]] = {
        Order: 2,
    }

    # --------------------------------------------------------------------- #
    # Transcoder configuration
    # --------------------------------------------------------------------- #

    def register_transcodings(self, transcoder: JSONTranscoder) -> None:
        """
        Register base transcodings (UUID, Decimal, Datetime) and also
        our custom value object transcodings (OrderLineItem).
        """
        # Call base implementation to register UUID, Decimal, Datetime, ...
        super().register_transcodings(transcoder)

        # Register custom transcoding for OrderLineItem so that snapshots
        # (which capture the full aggregate state) can be serialized.
        transcoder.register(OrderLineItemAsDict())

    # --------------------------------------------------------------------- #
    # Construction
    # --------------------------------------------------------------------- #

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # The read projection is a Postgres adapter, not part of the in-memory event store.
        # Tests using eventsourcing.popo therefore need no Postgres connection.
        import os
        self._order_head_projector = None
        if os.getenv("PERSISTENCE_MODULE", "eventsourcing.popo") == "eventsourcing.postgres":
            self._order_head_projector = OrderHeadProjector()
            self._order_head_projector.ensure_schema()

    # --------------------------------------------------------------------- #
    # Command methods
    # --------------------------------------------------------------------- #

    def create_order(
        self,
        consumer_id: str,
        restaurant_id: str,
        items: List[Dict[str, Any]],
    ) -> UUID:
        order = Order(
            consumer_id=consumer_id,
            restaurant_id=restaurant_id,
            items=items,
            aggregate_schema_version=Order.AGGREGATE_SCHEMA_VERSION,
            event_schema_version=Order.EVENT_SCHEMA_VERSION,
        )
        self.save(order)
        if self._order_head_projector is not None:
            self._order_head_projector.project_order(order)
        return order.id

    def add_item_to_order(
        self,
        order_id: UUID,
        menu_item_id: str,
        name: str,
        price: float,
        quantity: int,
        expected_version: Optional[int] = None,
    ) -> None:
        order: Order = self.repository.get(order_id)

        if expected_version is not None and order.version != expected_version:
            raise ConcurrencyError(
                f"Version mismatch: expected {expected_version}, found {order.version}"
            )

        order.add_item_to_order(
            menu_item_id=menu_item_id,
            name=name,
            price=price,
            quantity=quantity,
            event_schema_version=Order.EVENT_SCHEMA_VERSION,
        )

        try:
            self.save(order)
        except IntegrityError as e:
            # DB-level optimistic locking (unique constraint on originator_id + version).
            raise ConcurrencyError("Optimistic locking failed") from e

        if self._order_head_projector is not None:
            self._order_head_projector.project_order(order)

    def remove_item_from_order(
        self,
        order_id: UUID,
        menu_item_id: str,
        expected_version: Optional[int] = None,
    ) -> None:
        order: Order = self.repository.get(order_id)

        if expected_version is not None and order.version != expected_version:
            raise ConcurrencyError(
                f"Version mismatch: expected {expected_version}, found {order.version}"
            )

        order.remove_item_from_order(
            menu_item_id=menu_item_id,
            event_schema_version=Order.EVENT_SCHEMA_VERSION,
        )

        try:
            self.save(order)
        except IntegrityError as e:
            raise ConcurrencyError("Optimistic locking failed") from e

        if self._order_head_projector is not None:
            self._order_head_projector.project_order(order)

    def approve_order(
        self,
        order_id: UUID,
        expected_version: Optional[int] = None,
    ) -> None:
        order: Order = self.repository.get(order_id)

        if expected_version is not None and order.version != expected_version:
            raise ConcurrencyError(
                f"Version mismatch: expected {expected_version}, found {order.version}"
            )

        order.approve(event_schema_version=Order.EVENT_SCHEMA_VERSION)

        try:
            self.save(order)
        except IntegrityError as e:
            raise ConcurrencyError("Optimistic locking failed") from e

        if self._order_head_projector is not None:
            self._order_head_projector.project_order(order)

    def cancel_order(
        self,
        order_id: UUID,
        expected_version: Optional[int] = None,
    ) -> None:
        order: Order = self.repository.get(order_id)

        if expected_version is not None and order.version != expected_version:
            raise ConcurrencyError(
                f"Version mismatch: expected {expected_version}, found {order.version}"
            )

        order.cancel(event_schema_version=Order.EVENT_SCHEMA_VERSION)

        try:
            self.save(order)
        except IntegrityError as e:
            raise ConcurrencyError("Optimistic locking failed") from e

        if self._order_head_projector is not None:
            self._order_head_projector.project_order(order)

    def upgrade_order_schema(
        self,
        order_id: UUID,
        target_aggregate_schema_version: int,
    ) -> None:
        """Example command that emits an OrderSchemaUpgraded event."""
        order: Order = self.repository.get(order_id)
        if order.aggregate_schema_version >= target_aggregate_schema_version:
            return

        order.upgrade_schema(
            new_aggregate_schema_version=target_aggregate_schema_version
        )

        self.save(order)
        if self._order_head_projector is not None:
            self._order_head_projector.project_order(order)

    # --------------------------------------------------------------------- #
    # Query methods
    # --------------------------------------------------------------------- #

    def get_order(self, order_id: UUID) -> Order:
        return self.repository.get(order_id)

    def get_order_version(self, order_id: UUID, version: int) -> Order:
        """Return the historic state of the aggregate at the given version."""
        return self.repository.get(order_id, version=version)
