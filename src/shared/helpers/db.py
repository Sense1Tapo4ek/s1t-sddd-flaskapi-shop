import functools
from shared.generics.errors import DrivenPortError


def handle_db_errors(operation: str = ""):
    """Decorator that wraps DB exceptions into DrivenPortError."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except DrivenPortError:
                raise
            except Exception as e:
                label = operation or fn.__name__
                raise DrivenPortError(f"DB Error {label}: {e}")
        return wrapper
    return decorator
