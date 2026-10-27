# Pure transition table: stage -> expected reply -> new stage, command (if any).
# Failure compensation: reject ticket, then reject order.
TRANSITIONS = {
    ("VERIFY_CONSUMER", "ConsumerVerified"): ("CREATE_TICKET", "command.kitchen", "CreateTicket"),
    ("VERIFY_CONSUMER", "ConsumerRejected"): ("REJECTED", None, None),
    ("CREATE_TICKET", "TicketCreated"): ("AUTHORIZE_CARD", "command.accounting", "AuthorizeCard"),
    ("AUTHORIZE_CARD", "CardAuthorized"): ("APPROVE_TICKET", "command.kitchen", "ApproveTicket"),
    ("AUTHORIZE_CARD", "CardDeclined"): ("REJECT_TICKET", "command.kitchen", "RejectTicket"),
    ("APPROVE_TICKET", "TicketApproved"): ("APPROVED", None, None),
    ("REJECT_TICKET", "TicketRejected"): ("REJECTED", None, None),
}
