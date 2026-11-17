"""Reusable fixtures for domain, API and persistence tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.models import Address, Money, Order, OrderLineDraft
from app.infrastructure.db import Base
import app.infrastructure.orm_models  # noqa: F401


def address():
    return Address('Via Roma 1', 'Bari', '70100', 'IT')


def line(menu_id='PIZZA', price='10.00', qty=2, currency='EUR'):
    return OrderLineDraft(menu_id, menu_id.title(), Money(price, currency), qty)


def order():
    return Order.create('CUST_1', 'REST_1', [line()])


def sqlite_sessions():
    engine = create_engine('sqlite+pysqlite://',
                           connect_args={'check_same_thread': False},
                           poolclass=StaticPool, future=True)
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def line_payload(menu_id='PIZZA', price='10.00', qty=2, currency='EUR'):
    return {'menu_item_id': menu_id, 'name': menu_id.title(),
            'unit_price': {'amount': price, 'currency': currency}, 'quantity': qty}


def create_payload(lines=None):
    return {'consumer_id': 'CUST_1', 'restaurant_id': 'REST_1',
            'lines': [line_payload()] if lines is None else lines}
