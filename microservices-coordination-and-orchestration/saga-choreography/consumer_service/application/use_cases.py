from ports.repository import ConsumerRepository
class ConsumerUseCases:
    def __init__(self,repo:ConsumerRepository):self.repo=repo
    def handle(self,event,props):
        if event.get('type')!='OrderCreated':raise ValueError('Unexpected event')
        self.repo.evaluate_order(event,props)
