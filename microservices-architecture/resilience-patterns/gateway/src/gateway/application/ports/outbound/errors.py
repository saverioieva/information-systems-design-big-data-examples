class GatewayError(Exception):
    """Base exception exposed by outbound application ports."""


class ResourceNotFoundError(GatewayError):
    """The remote resource does not exist; this is not a transient failure."""


class DependencyUnavailableError(GatewayError):
    """A downstream dependency could not complete the requested operation."""


class TransientCallError(DependencyUnavailableError):
    """A downstream failure that may succeed if retried later."""


class CircuitOpenError(DependencyUnavailableError):
    """The circuit breaker rejected the call without contacting the service."""


class BulkheadRejectedError(DependencyUnavailableError):
    """The per-dependency bulkhead has no execution or queue capacity left."""
