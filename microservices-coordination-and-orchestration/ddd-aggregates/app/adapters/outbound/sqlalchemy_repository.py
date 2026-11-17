"""SQLAlchemy adapter: maps the whole aggregate to/from current-state rows."""

from typing import Optional

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session, selectinload

from app.domain.models import Address, ConcurrencyError, Money, Order, OrderLine
from app.infrastructure.orm_models import OrderLineModel, OrderModel
from app.ports.repository import OrderRepository


class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _address_values(address):
        return {
            'delivery_street': address.street if address else None,
            'delivery_city': address.city if address else None,
            'delivery_postal_code': address.postal_code if address else None,
            'delivery_country': address.country if address else None,
        }

    @staticmethod
    def _lines_values(order: Order):
        return [{
            'line_id': line.line_id, 'order_id': order.id,
            'menu_item_id': line.menu_item_id, 'name': line.name,
            'unit_price': line.unit_price.amount, 'currency': line.unit_price.currency,
            'quantity': line.quantity,
        } for line in order.lines]

    def add(self, order: Order) -> None:
        self.session.add(OrderModel(
            id=order.id, consumer_id=order.consumer_id,
            restaurant_id=order.restaurant_id, state=order.state, version_id=1,
            **self._address_values(order.address),
            lines=[OrderLineModel(**line) for line in self._lines_values(order)]
        ))

    def get(self, order_id: str) -> Optional[Order]:
        orm = self.session.execute(
            select(OrderModel).options(selectinload(OrderModel.lines)).where(OrderModel.id == order_id)
        ).scalar_one_or_none()
        if orm is None:
            return None
        address = None
        if orm.delivery_street is not None:
            address = Address(
                street=orm.delivery_street, city=orm.delivery_city,
                postal_code=orm.delivery_postal_code, country=orm.delivery_country
            )
        return Order.from_persistence(
            id=orm.id, consumer_id=orm.consumer_id, restaurant_id=orm.restaurant_id,
            state=orm.state, address=address,
            lines=[OrderLine(
                line_id=line.line_id, menu_item_id=line.menu_item_id, name=line.name,
                unit_price=Money(line.unit_price, line.currency), quantity=line.quantity
            ) for line in orm.lines],
            row_version=int(orm.version_id),
        )

    def save(self, order: Order) -> None:
        if order.row_version is None:
            raise ConcurrencyError('Missing version for an existing aggregate')
        result = self.session.execute(
            update(OrderModel)
            .where(OrderModel.id == order.id)
            .where(OrderModel.version_id == order.row_version)
            .values(
                state=order.state,
                version_id=OrderModel.version_id + 1,
                **self._address_values(order.address),
            )
        )
        if result.rowcount != 1:
            raise ConcurrencyError('Order has been modified concurrently')
        # Replacing the complete child collection is simple and safe in this
        # compact example; the stable line_id preserves domain identity.
        self.session.execute(delete(OrderLineModel).where(OrderLineModel.order_id == order.id))
        self.session.execute(insert(OrderLineModel), self._lines_values(order))
