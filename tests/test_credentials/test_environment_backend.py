"""Tests for environment variable backend."""

import os

import pytest

from repo_sapiens.credentials import EnvironmentBackend


class TestEnvironmentBackend:
    """Test EnvironmentBackend functionality."""

    @pytest.fixture
    def backend(self):
        """Create EnvironmentBackend instance."""
        return EnvironmentBackend()

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        """Clean up test environment variables after each test."""
        yield
        # Clean up any test variables
        test_vars = [key for key in os.environ if key.startswith("TEST_")]
        for var in test_vars:
            os.environ.pop(var, None)

    def test_backend_name(self, backend):
        """Test backend name property."""
        assert backend.name == "environment"

    def test_backend_always_available(self, backend):
        """Test environment backend is always available."""
        assert backend.available is True

    def test_get_existing_variable(self, backend):
        """Test retrieving existing environment variable."""
        os.environ["TEST_VAR"] = "test-value"

        result = backend.get("TEST_VAR")

        assert result == "test-value"

    def test_get_nonexistent_variable(self, backend):
        """Test retrieving nonexistent variable returns None."""
        result = backend.get("NONEXISTENT_VAR")

        assert result is None

    def test_set_variable(self, backend):
        """Test setting environment variable."""
        backend.set("TEST_VAR", "new-value")

        assert os.environ["TEST_VAR"] == "new-value"

    def test_set_empty_value_raises_error(self, backend):
        """Test setting empty value raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            backend.set("TEST_VAR", "")

    def test_delete_existing_variable(self, backend):
        """Test deleting existing variable."""
        os.environ["TEST_VAR"] = "value"

        result = backend.delete("TEST_VAR")

        assert result is True
        assert "TEST_VAR" not in os.environ

    def test_delete_nonexistent_variable(self, backend):
        """Test deleting nonexistent variable returns False."""
        result = backend.delete("NONEXISTENT_VAR")

        assert result is False

    def test_roundtrip(self, backend):
        """Test full lifecycle: set, get, delete."""
        # Set
        backend.set("TEST_TOKEN", "secret-123")

        # Get
        value = backend.get("TEST_TOKEN")
        assert value == "secret-123"

        # Delete
        deleted = backend.delete("TEST_TOKEN")
        assert deleted is True

        # Verify deleted
        value = backend.get("TEST_TOKEN")
        assert value is None

    def test_overwrite_existing_variable(self, backend):
        """Test overwriting existing variable."""
        backend.set("TEST_VAR", "value1")
        backend.set("TEST_VAR", "value2")

        assert backend.get("TEST_VAR") == "value2"
