"""Relational *current-state* storage (not an Event Store)."""

from sqlalchemy import Column, DateTime, Enum as SqlEnum, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import relationship

from app.domain.models import OrderState
from .db import Base


class OrderModel(Base):
    __tablename__ = 'orders'

    id = Column(String, primary_key=True)
    consumer_id = Column(String, nullable=False)
    restaurant_id = Column(String, nullable=False)
    state = Column(SqlEnum(OrderState), nullable=False)
    version_id = Column(Integer, nullable=False, default=1)
    delivery_street = Column(String, nullable=True)
    delivery_city = Column(String, nullable=True)
    delivery_postal_code = Column(String, nullable=True)
    delivery_country = Column(String, nullable=True)

    lines = relationship(
        'OrderLineModel', back_populates='order', cascade='all, delete-orphan',
        lazy='selectin', order_by='OrderLineModel.menu_item_id'
    )


class OrderLineModel(Base):
    __tablename__ = 'order_lines'

    line_id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, index=True)
    menu_item_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    quantity = Column(Integer, nullable=False)

    order = relationship('OrderModel', back_populates='lines')


class IntegrationOutboxModel(Base):
    __tablename__ = 'integration_outbox'

    event_id = Column(String, primary_key=True)
    aggregate_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
