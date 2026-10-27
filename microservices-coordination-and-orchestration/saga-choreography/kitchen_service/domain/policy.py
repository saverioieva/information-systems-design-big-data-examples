"""Pure ticket-state policy."""
def ticket_state(route:str)->str:
    return {'order.created':'CREATE_PENDING',
            'accounting.creditCardAuthorized':'TICKET_ACCEPTED',
            'accounting.creditCardAuthorizationFailed':'REJECTED'}[route]
