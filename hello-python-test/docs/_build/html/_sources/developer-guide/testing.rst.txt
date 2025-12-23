Testing Guide
==============

repo-sapiens uses pytest for testing. This guide covers testing best practices and infrastructure.

Testing Setup
~~~~~~~~~~~~~

**Install Testing Dependencies**

.. code-block:: bash

   pip install -e ".[dev]"

Or individually:

.. code-block:: bash

   pip install pytest pytest-cov pytest-xdist pytest-timeout

**Verify Setup**

.. code-block:: bash

   pytest --version

Running Tests
~~~~~~~~~~~~~

**Run All Tests**

.. code-block:: bash

   pytest

**Run with Verbose Output**

.. code-block:: bash

   pytest -v

**Run Specific Test**

.. code-block:: bash

   pytest tests/test_core.py
   pytest tests/test_core.py::test_greet

**Run with Coverage**

.. code-block:: bash

   pytest --cov=repo_sapiens
   pytest --cov=repo_sapiens --cov-report=html

**Run Tests in Parallel**

.. code-block:: bash

   pytest -n auto  # Uses pytest-xdist

**Run with Timeout**

.. code-block:: bash

   pytest --timeout=10  # 10 second timeout per test

Writing Tests
~~~~~~~~~~~~~

**Test Structure**

Create tests in the ``tests/`` directory with ``test_*.py`` naming:

.. code-block:: python

   # tests/test_core.py
   import pytest
   from repo_sapiens import greet, get_greeting

   def test_get_greeting_default():
       """Test get_greeting with default name."""
       result = get_greeting()
       assert result == "Hello, World!"

   def test_get_greeting_custom_name():
       """Test get_greeting with custom name."""
       result = get_greeting("Alice")
       assert result == "Hello, Alice!"

**Test Functions**

Test functions should:

- Start with ``test_``
- Have descriptive names
- Test one thing
- Be isolated and independent
- Clean up after themselves

**Using Fixtures**

Fixtures provide reusable test setup:

.. code-block:: python

   import pytest

   @pytest.fixture
   def sample_name():
       """Provide a sample name for tests."""
       return "TestUser"

   def test_with_fixture(sample_name):
       from repo_sapiens import get_greeting
       result = get_greeting(sample_name)
       assert "TestUser" in result

**Parametrized Tests**

Test multiple inputs with one test:

.. code-block:: python

   import pytest
   from repo_sapiens import get_greeting

   @pytest.mark.parametrize("name,expected", [
       ("World", "Hello, World!"),
       ("Alice", "Hello, Alice!"),
       ("Bob", "Hello, Bob!"),
   ])
   def test_get_greeting(name, expected):
       assert get_greeting(name) == expected

**Testing Exceptions**

Test that functions raise appropriate errors:

.. code-block:: python

   import pytest
   from repo_sapiens.core import some_function

   def test_raises_value_error():
       with pytest.raises(ValueError):
           some_function(invalid_input)

**Testing Output (stdout)**

.. code-block:: python

   from io import StringIO
   import sys
   from repo_sapiens import greet

   def test_greet_output(capsys):
       """Test greet function output."""
       greet("World")
       captured = capsys.readouterr()
       assert "Hello, World!" in captured.out

Coverage Analysis
~~~~~~~~~~~~~~~~~

**Generate Coverage Report**

.. code-block:: bash

   pytest --cov=repo_sapiens --cov-report=term-missing

**Generate HTML Coverage Report**

.. code-block:: bash

   pytest --cov=repo_sapiens --cov-report=html
   # Open htmlcov/index.html in browser

**Set Coverage Threshold**

.. code-block:: bash

   pytest --cov=repo_sapiens --cov-fail-under=80

Continuous Integration
~~~~~~~~~~~~~~~~~~~~~~

Tests run automatically on:

- Every push to repository
- Every pull request
- Scheduled nightly runs

Check ``.github/workflows/`` for CI configuration.

Test Organization
~~~~~~~~~~~~~~~~~

.. code-block:: text

   tests/
   ├── test_core.py           - Core module tests
   ├── conftest.py            - Shared fixtures
   └── fixtures/
       └── sample_data.py     - Test data

**conftest.py**

Shared fixtures go in ``conftest.py``:

.. code-block:: python

   # tests/conftest.py
   import pytest

   @pytest.fixture
   def temp_file(tmp_path):
       """Create a temporary file for testing."""
       file = tmp_path / "test.txt"
       file.write_text("test content")
       return file

**Markers**

Use markers to categorize tests:

.. code-block:: python

   import pytest

   @pytest.mark.slow
   def test_slow_operation():
       pass

   @pytest.mark.integration
   def test_with_external_service():
       pass

Run specific markers:

.. code-block:: bash

   pytest -m slow
   pytest -m "not slow"

Best Practices
~~~~~~~~~~~~~~

**Do**

- ✓ Test one thing per test
- ✓ Use descriptive names
- ✓ Use fixtures for setup
- ✓ Test both happy path and errors
- ✓ Keep tests independent
- ✓ Use parametrize for multiple inputs
- ✓ Test edge cases
- ✓ Mock external dependencies

**Don't**

- ✗ Use ``test_*`` for non-test code
- ✗ Write tests that depend on execution order
- ✗ Use magic numbers without explanation
- ✗ Test implementation details
- ✗ Mock everything (only external dependencies)
- ✗ Write slow tests without ``@pytest.mark.slow``

Advanced Testing
~~~~~~~~~~~~~~~~

**Mocking**

.. code-block:: python

   from unittest.mock import patch, MagicMock
   from repo_sapiens import get_greeting

   def test_with_mock():
       with patch('repo_sapiens.core.some_function') as mock:
           mock.return_value = "mocked"
           result = get_greeting("test")
           mock.assert_called_once()

**Doctest**

Tests in docstrings:

.. code-block:: python

   def my_function(x: int) -> int:
       """
       Example function.

       >>> my_function(5)
       10
       """
       return x * 2

Run doctests:

.. code-block:: bash

   pytest --doctest-modules src/

**Property-Based Testing**

.. code-block:: bash

   pip install hypothesis

.. code-block:: python

   from hypothesis import given
   import hypothesis.strategies as st

   @given(st.text())
   def test_any_string(s):
       from repo_sapiens import get_greeting
       result = get_greeting(s)
       assert isinstance(result, str)

Troubleshooting
~~~~~~~~~~~~~~~

**Tests Not Found**

Ensure files are named ``test_*.py`` or ``*_test.py``:

.. code-block:: bash

   pytest --collect-only  # List all discovered tests

**Import Errors**

Install package in development mode:

.. code-block:: bash

   pip install -e .

**Fixture Not Found**

Fixtures must be in:

- Same module as test
- ``conftest.py`` in test directory
- ``conftest.py`` in parent directories

Test Coverage Goals
~~~~~~~~~~~~~~~~~~~

Current targets:

- Core module: 100% coverage (simple functions)
- Overall: >90% coverage

Coverage is measured with:

.. code-block:: bash

   pytest --cov=repo_sapiens --cov-report=term-missing

Performance Testing
~~~~~~~~~~~~~~~~~~~

**Measure Test Speed**

.. code-block:: bash

   pytest --durations=10  # Show 10 slowest tests

**Optimize Slow Tests**

- Use fixtures to avoid repeated setup
- Mock slow operations
- Mark slow tests: ``@pytest.mark.slow``

Next Steps
~~~~~~~~~~

- See :doc:`/developer-guide/contributing` for contribution guidelines
- Review :doc:`/developer-guide/development` for development setup
- Check :doc:`/api/core` for API being tested

.. note::

   Good tests make development faster and safer. Invest time in comprehensive test coverage!
