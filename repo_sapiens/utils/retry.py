"""Retry utilities for handling transient failures.

Provides decorators and utilities for retrying async operations with
exponential backoff. Useful for handling transient failures in network
operations, API calls, and other unreliable operations.

Key Features:
    - Exponential backoff with configurable base factor
    - Configurable exception filtering (only retry specific exceptions)
    - Maximum attempt limiting
    - Structured logging of retry attempts

Key Exports:
    async_retry: Decorator for adding retry logic to async functions.

Example:
    >>> from repo_sapiens.utils.retry import async_retry
    >>>
    >>> @async_retry(max_attempts=3, backoff_factor=2.0)
    ... async def fetch_data(url: str) -> dict:
    ...     async with aiohttp.ClientSession() as session:
    ...         async with session.get(url) as response:
    ...             return await response.json()

Thread Safety:
    The retry decorator is stateless and safe for concurrent use.
    Each decorated function call maintains its own retry state.

Backoff Formula:
    delay = backoff_factor ** attempt_number
    For backoff_factor=2.0: 2s, 4s, 8s, 16s, ...
"""

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

    Wraps an async function to automatically retry on specified exceptions.
    Uses exponential backoff between attempts to avoid overwhelming services
    that may be temporarily unavailable.

    Args:
        max_attempts: Maximum number of attempts before giving up. The
            function will be called at most max_attempts times. Default
            is 3 (original attempt + 2 retries).
        backoff_factor: Base for exponential backoff calculation. The delay
            before attempt N is backoff_factor^N seconds. Default is 2.0,
            giving delays of 2s, 4s, 8s, etc.
        exceptions: Tuple of exception types to catch and retry. Only
            exceptions in this tuple (or subclasses) will trigger a retry.
            Other exceptions propagate immediately. Default is (Exception,)
            which catches all exceptions.

    Returns:
        A decorator function that wraps async functions with retry logic.

    Raises:
        The last caught exception if all retry attempts are exhausted.
        Exceptions not in the exceptions tuple are raised immediately.

    Example:
        >>> # Basic usage - retry any exception up to 3 times
        >>> @async_retry()
        ... async def fetch_data():
        ...     return await some_api_call()

        >>> # Retry only connection errors, up to 5 times
        >>> @async_retry(
        ...     max_attempts=5,
        ...     backoff_factor=1.5,
        ...     exceptions=(ConnectionError, TimeoutError),
        ... )
        ... async def fetch_with_timeout():
        ...     return await unreliable_api_call()

        >>> # Aggressive retry for critical operations
        >>> @async_retry(max_attempts=10, backoff_factor=1.2)
        ... async def critical_operation():
        ...     return await must_succeed_operation()

    Warning:
        Be careful with long retry chains. With max_attempts=5 and
        backoff_factor=2.0, the total wait time before final failure is:
        2 + 4 + 8 + 16 = 30 seconds (not counting execution time).

    Note:
        The decorator logs each retry attempt at WARNING level and logs
        exhausted retries at ERROR level using structlog. This makes it
        easy to monitor retry patterns in production.

    See Also:
        - tenacity: A more feature-rich retry library if you need
          more advanced retry patterns (jitter, retry conditions, etc.)
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
