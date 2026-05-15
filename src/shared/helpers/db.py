import functools
import logging

from sqlalchemy.exc import IntegrityError

from shared.generics.errors import (
    ApplicationError,
    DomainError,
    DrivenPortError,
)

logger = logging.getLogger("db")


def handle_db_errors(operation: str = ""):
    """Decorator that wraps DB exceptions into DrivenPortError.

    Semantic LayerError subtypes (DomainError, ApplicationError) and
    raw LookupError are re-raised unchanged — the bulk runner and
    other callers rely on per-row business errors propagating intact.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (DrivenPortError, DomainError, ApplicationError, LookupError):
                raise
            except IntegrityError:
                label = operation or fn.__name__
                logger.warning("DB integrity error during %s", label)
                raise DrivenPortError("Database integrity constraint failed") from None
            except Exception as e:
                label = operation or fn.__name__
                logger.error("DB error during %s: %s", label, type(e).__name__)
                raise DrivenPortError(f"Database operation failed: {label}") from None
        return wrapper
    return decorator
