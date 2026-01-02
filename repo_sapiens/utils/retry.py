"""Retry utilities for handling transient failures."""

import asyncio
import functools
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

log = structlog.get_logger(__name__)

T = TypeVar("T")


def async_retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for async functions with exponential backoff retry logic.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (delay = backoff_factor ^ attempt)
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated async function with retry logic

    Example:
        @async_retry(max_attempts=3, backoff_factor=2.0)
        async def fetch_data():
            # This will retry up to 3 times with exponential backoff
            return await some_api_call()
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        log.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=attempt,
                            error=str(e),
                        )
                        raise

                    delay = backoff_factor**attempt
                    log.warning(
                        "retry_attempt",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)

            # This should never be reached, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error")

        return wrapper

    return decorator
