"""Pure state machine for a Cancel Order Saga.

CancelOrder is a second business workflow, not an HTTP status update: it
voids the existing card authorization and rejects the kitchen ticket before
marking cancellation complete.  The order remains CANCELLATION_PENDING while
those asynchronous compensation commands execute.
"""
from app.domain.state_machine import Transition


class CancelOrderStateMachine:
    TRANSITIONS = {
        ('VOID_AUTHORIZATION', 'AuthorizationVoided'): Transition(
            'REJECT_TICKET', 'command.kitchen', 'RejectTicket'),
        ('REJECT_TICKET', 'TicketRejected'): Transition('CANCELLED', None, None),
    }

    def advance(self, stage: str | None, reply: str) -> Transition | None:
        return self.TRANSITIONS.get((stage, reply))

    def as_rows(self) -> list[dict]:
        return [dict(from_stage=stage, on_reply=reply, to_stage=t.stage,
                     route=t.route, command=t.command)
                for (stage, reply), t in self.TRANSITIONS.items()]
