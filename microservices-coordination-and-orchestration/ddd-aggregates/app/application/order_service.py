"""Use cases coordinate transactions; only Order decides domain changes."""

from app.domain.models import Address, ConcurrencyError, Money, Order, OrderLineDraft


class OrderService:
    def __init__(self, uow_factory):
        self.uow_factory = uow_factory

    @staticmethod
    def _draft(data: dict) -> OrderLineDraft:
        amount = data['unit_price']
        if isinstance(amount, dict):
            amount = Money(**amount)
        return OrderLineDraft(
            menu_item_id=data['menu_item_id'], name=data['name'],
            unit_price=amount, quantity=data['quantity']
        )

    @staticmethod
    def _check_version(order: Order, expected_version):
        if expected_version is not None and order.row_version != expected_version:
            raise ConcurrencyError('Stale expected_version; reload the order')

    @staticmethod
    def _load(uow, order_id: str) -> Order:
        order = uow.repo.get(order_id)
        if order is None:
            raise LookupError('Order not found')
        return order

    def create(self, consumer_id: str, restaurant_id: str, lines: list[dict]):
        with self.uow_factory() as uow:
            order = Order.create(consumer_id, restaurant_id, [self._draft(line) for line in lines])
            uow.repo.add(order)
            uow.add_events(order.collect_domain_events())
            uow.commit()
            uow.expire_all()
            return uow.repo.get(order.id)

    def get(self, order_id: str):
        with self.uow_factory() as uow:
            return uow.repo.get(order_id)

    def _mutate(self, order_id: str, expected_version, method, *args):
        with self.uow_factory() as uow:
            order = self._load(uow, order_id)
            self._check_version(order, expected_version)
            getattr(order, method)(*args)
            events = order.collect_domain_events()
            if events:  # a no-op does not advance the version
                uow.repo.save(order)
                uow.add_events(events)
                uow.commit()
                uow.expire_all()
                return uow.repo.get(order.id)
            return order

    def add_line(self, order_id: str, line: dict, expected_version=None):
        return self._mutate(order_id, expected_version, 'add_line', self._draft(line))

    def change_quantity(self, order_id: str, line_id: str, quantity: int, expected_version=None):
        return self._mutate(order_id, expected_version, 'change_line_quantity', line_id, quantity)

    def remove_line(self, order_id: str, line_id: str, expected_version=None):
        return self._mutate(order_id, expected_version, 'remove_line', line_id)

    def change_address(self, order_id: str, address: dict, expected_version=None):
        return self._mutate(order_id, expected_version, 'change_delivery_address', Address(**address))

    def approve(self, order_id: str, expected_version=None):
        return self._mutate(order_id, expected_version, 'approve')

    def cancel(self, order_id: str, expected_version=None):
        return self._mutate(order_id, expected_version, 'cancel')
