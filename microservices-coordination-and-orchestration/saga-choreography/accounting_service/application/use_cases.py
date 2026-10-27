"""Apply only supported saga events; infra-free application routing."""
from ports.repository import AccountingRepository
ROUTES={'order.created','consumer.verified','consumer.verificationFailed','kitchen.ticketCreated'}
class AccountingUseCases:
    def __init__(self,repo:AccountingRepository):self.repo=repo
    def handle(self,event,props,route):
        if route not in ROUTES:raise ValueError(f'Unexpected saga event: {route}')
        self.repo.apply_event(event,props,route)
