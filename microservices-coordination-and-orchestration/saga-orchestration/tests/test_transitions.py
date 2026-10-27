import unittest
from app.domain.transitions import TRANSITIONS

class TestTransitions(unittest.TestCase):
    def test_success(self):
        self.assertEqual(TRANSITIONS[("VERIFY_CONSUMER", "ConsumerVerified")][0], "CREATE_TICKET")
        self.assertEqual(TRANSITIONS[("APPROVE_TICKET", "TicketApproved")][0], "APPROVED")

    def test_compensation(self):
        self.assertEqual(TRANSITIONS[("AUTHORIZE_CARD", "CardDeclined")],
                         ("REJECT_TICKET", "command.kitchen", "RejectTicket"))
        self.assertEqual(TRANSITIONS[("REJECT_TICKET", "TicketRejected")][0], "REJECTED")

    def test_no_stale_transition(self):
        self.assertNotIn(("APPROVED", "CardDeclined"), TRANSITIONS)

if __name__ == '__main__': unittest.main()
