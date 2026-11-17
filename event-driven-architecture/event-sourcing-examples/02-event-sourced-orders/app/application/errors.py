"""Business-facing errors independent of the eventsourcing library."""
class ConcurrencyError(Exception):
    pass

class OrderNotFound(LookupError):
    pass
