"""Environment variable backend for CI/CD and containerized environments."""

import logging
import os

logger = logging.getLogger(__name__)


class EnvironmentBackend:
    """Environment variable credential storage.

    This backend is ideal for:
    - CI/CD pipelines (GitHub Actions, Gitea Actions)
    - Docker containers
    - Serverless functions
    - Any environment where secrets are injected as env vars

    Security Considerations:
    - Environment variables are visible to all processes
    - May be logged in process listings
    - Not persisted across sessions
    - Suitable for temporary/ephemeral environments

    Example:
        >>> import os
        >>> os.environ['GITEA_API_TOKEN'] = 'ghp_abc123'
        >>> backend = EnvironmentBackend()
        >>> token = backend.get('GITEA_API_TOKEN')
    """

    @property
    def name(self) -> str:
        """Get backend identifier.

        Returns:
            Backend name constant "environment"
        """
        return "environment"

    @property
    def available(self) -> bool:
        """Environment backend is always available."""
        return True

    def get(self, var_name: str) -> str | None:
        """Retrieve credential from environment variable.

        Args:
            var_name: Environment variable name (e.g., 'GITEA_API_TOKEN')

        Returns:
            Credential value or None if not set

        Note:
            This method uses a single parameter (var_name) unlike other
            backends that use (service, key) to match environment variable
            semantics.
        """
        value = os.getenv(var_name)

        if value is not None:
            logger.debug(f"Retrieved credential from environment: {var_name}")

        return value

    def set(self, var_name: str, value: str) -> None:
        """Set environment variable.

        Args:
            var_name: Environment variable name
            value: Credential value

        Note:
            Changes only affect the current process and child processes.
            Not persisted across sessions.
        """
        if not value:
            raise ValueError("Credential value cannot be empty")

        os.environ[var_name] = value
        logger.debug(f"Set environment variable: {var_name}")

    def delete(self, var_name: str) -> bool:
        """Remove environment variable.

        Args:
            var_name: Environment variable name

        Returns:
            True if deleted, False if not found
        """
        if var_name in os.environ:
            del os.environ[var_name]
            logger.debug(f"Deleted environment variable: {var_name}")
            return True
        return False
