from ports.repository import KitchenRepository
from domain.policy import ticket_state
class KitchenUseCases:
    def __init__(self,repo:KitchenRepository):self.repo=repo
    def handle(self,event,props,route):
        state=ticket_state(route)
        self.repo.apply_event(event,props,route,state)
