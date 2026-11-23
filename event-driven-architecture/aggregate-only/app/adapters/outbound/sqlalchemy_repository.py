from typing import Optional
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.domain.models import Order, OrderLineItem, ConcurrencyError
from app.ports.repository import OrderRepository as OrderRepositoryInterface
from app.infrastructure.orm_models import OrderModel, OrderLineItemModel

class SqlAlchemyOrderRepository(OrderRepositoryInterface):
    """Store current state in SQL rows, protected by a version compare-and-swap."""
    def __init__(self, session: Session):
        self.session = session

    def add(self, order: Order) -> None:
        orm = OrderModel(id=order.id, consumer_id=order.consumer_id,
                         restaurant_id=order.restaurant_id, state=order.state, version=1)
        orm.line_items = [OrderLineItemModel(menu_item_id=i.menu_item_id, name=i.name,
                          price=i.price, quantity=i.quantity) for i in order.line_items]
        self.session.add(orm)

    def get(self, order_id: str) -> Optional[Order]:
        orm = self.session.get(OrderModel, order_id)
        if orm is None:
            return None
        return Order(id=orm.id, consumer_id=orm.consumer_id, restaurant_id=orm.restaurant_id,
                     state=orm.state, line_items=[OrderLineItem(i.menu_item_id,i.name,i.price,i.quantity)
                     for i in orm.line_items], row_version=orm.version)

    def save(self, order: Order) -> None:
        if order.row_version is None:
            raise ConcurrencyError("Missing row_version")
        # WHERE version = expected is atomic, not a separate read followed by a write.
        result = self.session.execute(update(OrderModel).where(
            OrderModel.id == order.id, OrderModel.version == order.row_version
        ).values(consumer_id=order.consumer_id, restaurant_id=order.restaurant_id,
                 state=order.state, version=OrderModel.version + 1))
        if result.rowcount != 1:
            raise ConcurrencyError("Stale version: order modified concurrently")
        self.session.query(OrderLineItemModel).filter_by(order_id=order.id).delete(synchronize_session=False)
        self.session.add_all([OrderLineItemModel(order_id=order.id, menu_item_id=i.menu_item_id,
                              name=i.name, price=i.price, quantity=i.quantity)
                              for i in order.line_items])

    def delete(self, order_id: str) -> None:
        orm = self.session.get(OrderModel, order_id)
        if orm is not None:
            self.session.delete(orm)
