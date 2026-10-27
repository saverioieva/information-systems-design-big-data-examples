"""The final order state is a pure business decision."""
def status_for_accounting_event(route: str) -> str:
    if route=='accounting.creditCardAuthorized':return 'APPROVED'
    if route=='accounting.creditCardAuthorizationFailed':return 'REJECTED'
    raise ValueError(f'Unsupported accounting event: {route}')
