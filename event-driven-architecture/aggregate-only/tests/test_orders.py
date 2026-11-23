import os
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.domain.models import Order, OrderLineItem, OrderState, ConcurrencyError
from app.infrastructure.db import Base
import app.infrastructure.orm_models  # noqa: F401
from app.adapters.outbound.sqlalchemy_repository import SqlAlchemyOrderRepository

@pytest.fixture
def engine():
    engine=create_engine("sqlite+pysqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

def item(sku="pizza"):
    return OrderLineItem(sku,"Pizza",5.0,2)

def test_order_rules():
    with pytest.raises(ValueError):
        Order.create("c","r",[])
    order=Order.create("c","r",[item()])
    order.approve()
    assert order.state == OrderState.APPROVED
    with pytest.raises(ValueError):
        order.add_item_to_order("water","Water",1.0,1)

def test_state_persistence_and_stale_update(engine):
    with Session(engine) as s:
        repo=SqlAlchemyOrderRepository(s)
        created=Order.create("c","r",[item()]); repo.add(created); s.commit()
        assert repo.get(created.id).row_version==1
    with Session(engine) as s1, Session(engine) as s2:
        repo1=SqlAlchemyOrderRepository(s1); repo2=SqlAlchemyOrderRepository(s2)
        first=repo1.get(created.id); stale=repo2.get(created.id)
        first.add_item_to_order("water","Water",1,1)
        repo1.save(first); s1.commit()
        stale.cancel()
        with pytest.raises(ConcurrencyError):
            repo2.save(stale)
        s2.rollback()
    with Session(engine) as s:
        saved=SqlAlchemyOrderRepository(s).get(created.id)
        assert saved.row_version==2
        assert saved.state == OrderState.APPROVAL_PENDING
        assert {i.menu_item_id for i in saved.line_items} == {"pizza","water"}
