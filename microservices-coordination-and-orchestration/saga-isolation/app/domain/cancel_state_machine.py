"""Pure CancelOrder transitions, including the Pessimistic View variant.

The ordinary cancellation sequence remains VoidAuthorization -> RejectTicket ->
CANCELLED. Pessimistic View instead uses a successful Kitchen RejectTicket as
its pivot: while the order is CANCELLATION_PENDING, Kitchen makes the decision
irreversible. The post-pivot steps set the Order to CANCELLED *before* Accounting
voids the authorization; both steps are retriable and idempotent.

This example models a successful pivot. It does not implement business rejection
of Kitchen cancellation or its compensating rollback to the previous state.
"""
from app.domain.state_machine import Transition


class CancelOrderStateMachine:
    TRANSITIONS = {
        ('VOID_AUTHORIZATION', 'AuthorizationVoided'): Transition(
            'REJECT_TICKET', 'command.kitchen', 'RejectTicket'),
        ('REJECT_TICKET', 'TicketRejected'): Transition('CANCELLED', None, None),
        # Pessimistic View: the Kitchen success is the business pivot.
        ('REJECT_TICKET_PIVOT', 'TicketRejected'): Transition(
            'SET_CANCELLED', 'command.order', 'SetCancelled'),
        ('SET_CANCELLED', 'OrderCancelled'): Transition(
            'VOID_AUTHORIZATION_RETRIABLE', 'command.accounting', 'VoidAuthorization'),
        ('VOID_AUTHORIZATION_RETRIABLE', 'AuthorizationVoided'): Transition(
            'CANCELLED', None, None),
    }

    def advance(self, stage: str | None, reply: str) -> Transition | None:
        return self.TRANSITIONS.get((stage, reply))

    def as_rows(self) -> list[dict]:
        return [dict(from_stage=stage, on_reply=reply, to_stage=t.stage,
                     route=t.route, command=t.command)
                for (stage, reply), t in self.TRANSITIONS.items()]
