"""Pure Create Order Saga state machine.

A transition is: (current stage, reply received) -> (new stage, route, command).
The route is None only for a terminal state.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Transition:
    stage: str
    route: str | None
    command: str | None


class SagaStateMachine:
    TRANSITIONS = {
        ('VERIFY_CONSUMER', 'ConsumerVerified'): Transition('CREATE_TICKET', 'command.kitchen', 'CreateTicket'),
        ('VERIFY_CONSUMER', 'ConsumerRejected'): Transition('REJECT_ORDER', 'command.order', 'RejectOrder'),
        ('VERIFY_CONSUMER', 'ConsumerVerificationFailed'): Transition('REJECT_ORDER', 'command.order', 'RejectOrder'),
        ('CREATE_TICKET', 'TicketCreated'): Transition('AUTHORIZE_CARD', 'command.accounting', 'AuthorizeCard'),
        ('CREATE_TICKET', 'TicketCreationFailed'): Transition('REJECT_ORDER', 'command.order', 'RejectOrder'),
        ('AUTHORIZE_CARD', 'CardAuthorized'): Transition('APPROVE_TICKET', 'command.kitchen', 'ApproveTicket'),
        ('AUTHORIZE_CARD', 'CardDeclined'): Transition('REJECT_TICKET', 'command.kitchen', 'RejectTicket'),
        ('AUTHORIZE_CARD', 'CardAuthorizationFailed'): Transition('REJECT_TICKET', 'command.kitchen', 'RejectTicket'),
        ('REJECT_TICKET', 'TicketRejected'): Transition('REJECT_ORDER', 'command.order', 'RejectOrder'),
        ('REJECT_ORDER', 'OrderRejected'): Transition('REJECTED', None, None),
        ('APPROVE_TICKET', 'TicketApproved'): Transition('APPROVE_ORDER', 'command.order', 'ApproveOrder'),
        ('APPROVE_ORDER', 'OrderApproved'): Transition('APPROVED', None, None),
    }

    def advance(self, current_stage: str | None, reply: str) -> Transition | None:
        return self.TRANSITIONS.get((current_stage, reply))

    def as_rows(self) -> list[dict]:
        return [dict(from_stage=stage, on_reply=reply, to_stage=t.stage,
                     route=t.route, command=t.command)
                for (stage, reply), t in self.TRANSITIONS.items()]
