from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import update

from app.domain.models import Order, OrderLineItem, ConcurrencyError
from app.ports.repository import OrderRepository as OrderRepositoryInterface
from app.infrastructure.orm_models import OrderModel, OrderLineItemModel


class SqlAlchemyOrderRepository(OrderRepositoryInterface):

    def __init__(self, session: Session):
        self.session = session

    def add(self, order: Order) -> None:
        orm = self._to_orm(order)
        self.session.add(orm)

    def get(self, order_id: str) -> Optional[Order]:
        orm = self.session.query(OrderModel).filter_by(id=order_id).one_or_none()
        if orm is None:
            return None
        return self._to_domain(orm)

    def save(self, order: Order) -> None:
        if order.row_version is None:
            raise ConcurrencyError("Missing row_version for optimistic locking")

        stmt = (
            update(OrderModel)
            .where(OrderModel.id == order.id)
            .where(OrderModel.version_id == order.row_version)
            .values(
                consumer_id=order.consumer_id,
                restaurant_id=order.restaurant_id,
                state=order.state,
                version_id=OrderModel.version_id + 1,
            )
        )

        result = self.session.execute(stmt)
        if result.rowcount == 0:
            raise ConcurrencyError("Order has been modified concurrently")

        self.session.query(OrderLineItemModel).filter_by(order_id=order.id).delete()

        for li in order.line_items:
            self.session.add(
                OrderLineItemModel(
                    order_id=order.id,
                    menu_item_id=li.menu_item_id,
                    name=li.name,
                    price=li.price,
                    quantity=li.quantity,
                )
            )

    def delete(self, order_id: str) -> None:
        orm = self.session.query(OrderModel).filter_by(id=order_id).one_or_none()
        if orm:
            self.session.delete(orm)

    def _to_orm(self, order: Order) -> OrderModel:
        orm = OrderModel(
            id=order.id,
            consumer_id=order.consumer_id,
            restaurant_id=order.restaurant_id,
            state=order.state,
        )
        orm.line_items = [
            OrderLineItemModel(
                menu_item_id=li.menu_item_id,
                name=li.name,
                price=li.price,
                quantity=li.quantity,
            )
            for li in order.line_items
        ]
        return orm

    def _to_domain(self, orm: OrderModel) -> Order:
        return Order(
            id=orm.id,
            consumer_id=orm.consumer_id,
            restaurant_id=orm.restaurant_id,
            state=orm.state,
            line_items=[
                OrderLineItem(
                    menu_item_id=li.menu_item_id,
                    name=li.name,
                    price=li.price,
                    quantity=li.quantity,
                )
                for li in orm.line_items
            ],
            row_version=int(orm.version_id),
        )
