class LayerError(Exception):
    """
    Base class for all architectural errors.

    :param message: Human readable description.
    :param code: Machine readable slug (e.g. 'ORDER_NOT_FOUND').
    """

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class DomainError(LayerError):
    """
    Business rule violation (Invariant broken).
    HTTP Map: 409 Conflict or 422 Unprocessable Entity.
    """

    pass


class ApplicationError(LayerError):
    """
    Logic flow failure (Not Found, State invalid for action).
    HTTP Map: 404 Not Found or 400 Bad Request.
    """

    pass


class DrivingPortError(LayerError):
    """
    Failure at the entry gate (Validation, Schema).
    HTTP Map: 400 Bad Request.
    """

    pass


class DrivenPortError(LayerError):
    """
    Failure at the exit gate (Repository contract failed).
    HTTP Map: 500 Internal Server Error.
    """

    pass


class DrivingAdapterError(LayerError):
    """
    Failure in incoming infra (Auth header missing, URL malformed).
    HTTP Map: 401 Unauthorized / 403 Forbidden.
    """

    pass


class DrivenAdapterError(LayerError):
    """
    Failure in outgoing infra (DB down, 3rd party API timeout).
    HTTP Map: 503 Service Unavailable.
    """

    pass
