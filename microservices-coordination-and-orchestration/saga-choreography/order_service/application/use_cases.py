from domain.policy import status_for_accounting_event
from ports.repository import OrderRepository
class OrderUseCases:
    def __init__(self,repo:OrderRepository):self.repo=repo
    def create_order(self,customer_id,amount):
        return {'status':'ACCEPTED','orderId':self.repo.create(customer_id,amount)}
    def order(self,oid):return self.repo.get(oid)
    def orders(self):return self.repo.list()
    def accounting_result(self,event,route,props):
        self.repo.apply_result(event,props,status_for_accounting_event(route))
