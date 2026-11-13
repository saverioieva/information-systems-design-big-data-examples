import unittest
from app.domain.state_machine import SagaStateMachine, Transition


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.machine = SagaStateMachine()

    def test_success(self):
        self.assertEqual(self.machine.advance('VERIFY_CONSUMER', 'ConsumerVerified').stage, 'CREATE_TICKET')
        self.assertEqual(self.machine.advance('APPROVE_TICKET', 'TicketApproved'),
                         Transition('APPROVE_ORDER', 'command.order', 'ApproveOrder'))
        self.assertEqual(self.machine.advance('APPROVE_ORDER', 'OrderApproved').stage, 'APPROVED')

    def test_compensation(self):
        self.assertEqual(self.machine.advance('AUTHORIZE_CARD', 'CardDeclined'),
                         Transition('REJECT_TICKET', 'command.kitchen', 'RejectTicket'))
        self.assertEqual(self.machine.advance('REJECT_TICKET', 'TicketRejected'),
                         Transition('REJECT_ORDER', 'command.order', 'RejectOrder'))
        self.assertEqual(self.machine.advance('REJECT_ORDER', 'OrderRejected').stage, 'REJECTED')

    def test_ticket_creation_failure_waits_for_reject_reply(self):
        self.assertEqual(self.machine.advance('CREATE_TICKET', 'TicketCreationFailed'),
                         Transition('REJECT_ORDER', 'command.order', 'RejectOrder'))

    def test_invalid_consumer_waits_for_reject_reply(self):
        self.assertEqual(self.machine.advance('VERIFY_CONSUMER', 'ConsumerRejected').stage, 'REJECT_ORDER')

    def test_stale_reply_does_not_advance(self):
        self.assertIsNone(self.machine.advance('APPROVED', 'CardDeclined'))


if __name__ == '__main__':
    unittest.main()
