Development Guide
=================

This guide covers technical aspects of developing repo-sapiens.

Development Setup
~~~~~~~~~~~~~~~~~

**Prerequisites**

- Python 3.8 or higher
- pip and setuptools
- Git

**Initial Setup**

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/savorywatt/repo-sapiens.git
   cd repo-sapiens

   # Create virtual environment
   python -m venv venv
   source venv/bin/activate

   # Install in editable mode with dev dependencies
   pip install -e ".[dev]"

Project Structure
~~~~~~~~~~~~~~~~~

.. code-block:: text

   repo-sapiens/
   ├── src/
   │   └── repo_sapiens/
   │       ├── __init__.py      - Package exports
   │       └── core.py          - Core functionality
   ├── tests/
   │   └── test_*.py            - Test files
   ├── docs/
   │   ├── source/
   │   │   ├── conf.py          - Sphinx config
   │   │   ├── index.rst        - Main docs
   │   │   └── ...
   │   └── Makefile
   ├── pyproject.toml           - Project config
   ├── README.md
   ├── LICENSE
   └── .gitignore

Building the Package
~~~~~~~~~~~~~~~~~~~~

**Build Distribution**

.. code-block:: bash

   pip install build
   python -m build

This creates:

- ``dist/repo_sapiens-0.0.2.tar.gz`` - Source distribution
- ``dist/repo_sapiens-0.0.2-py3-none-any.whl`` - Wheel distribution

**Install Local Build**

.. code-block:: bash

   pip install dist/repo_sapiens-0.0.2-py3-none-any.whl

Building Documentation
~~~~~~~~~~~~~~~~~~~~~~

**Build HTML Documentation**

.. code-block:: bash

   cd docs
   make clean
   make html

Output is in ``docs/_build/html/index.html``

**View Documentation Locally**

.. code-block:: bash

   # Using Python's built-in server
   cd docs/_build/html
   python -m http.server 8000

   # Then visit http://localhost:8000

**Watch for Changes** (with sphinx-autobuild)

.. code-block:: bash

   pip install sphinx-autobuild
   cd docs
   sphinx-autobuild source _build/html

Version Management
~~~~~~~~~~~~~~~~~~

Version is stored in two places:

1. **pyproject.toml**: ``version = "0.0.2"``
2. **src/repo_sapiens/__init__.py**: ``__version__ = "0.0.1"``

Keep these synchronized! Update both when releasing.

Code Organization
~~~~~~~~~~~~~~~~~

**Module Responsibilities**

``repo_sapiens/__init__.py``
  - Package-level exports
  - Version information
  - High-level API

``repo_sapiens/core.py``
  - Core functionality
  - Basic utilities
  - Foundation for other modules

Future modules will handle:

- Configuration management
- Credential handling
- Git operations
- Template rendering
- CLI interface
- Domain models

**Adding New Functions**

1. Create function in appropriate module
2. Add docstring with Google style:

   .. code-block:: python

      def my_function(param: str) -> bool:
          """
          Short description.

          Longer description if needed.

          Args:
              param: Description of param

          Returns:
              Description of return value

          Raises:
              ValueError: When something is wrong

          Example:
              >>> my_function("test")
              True
          """

3. Add type hints
4. Export in ``__init__.py`` if public
5. Add tests
6. Update documentation

**Adding New Modules**

1. Create file in ``src/repo_sapiens/new_module.py``
2. Add docstring at module level
3. Import in ``src/repo_sapiens/__init__.py`` if public
4. Create documentation in ``docs/source/api/``
5. Add tests in ``tests/test_new_module.py``

Code Quality Tools
~~~~~~~~~~~~~~~~~~

**Formatting**

.. code-block:: bash

   # Format code with black
   pip install black
   black src/ tests/

**Linting**

.. code-block:: bash

   # Check with flake8
   pip install flake8
   flake8 src/ tests/

   # Or ruff (faster)
   pip install ruff
   ruff check src/ tests/

**Type Checking**

.. code-block:: bash

   # Check types with mypy
   pip install mypy
   mypy src/

**All Together**

.. code-block:: bash

   # Install pre-commit
   pip install pre-commit
   pre-commit install

   # Run all checks
   pre-commit run --all-files

Common Development Tasks
~~~~~~~~~~~~~~~~~~~~~~~~

**Run Tests**

.. code-block:: bash

   pytest
   pytest -v  # Verbose
   pytest -k test_name  # Specific test
   pytest --cov  # With coverage

**Clean Build Artifacts**

.. code-block:: bash

   rm -rf build/
   rm -rf dist/
   rm -rf *.egg-info
   rm -rf .pytest_cache
   rm -rf .mypy_cache

**Update Dependencies**

.. code-block:: bash

   pip list --outdated
   pip install --upgrade package-name

Debugging
~~~~~~~~~

**Using pdb**

.. code-block:: python

   import pdb; pdb.set_trace()  # Breakpoint

   # Commands: n (next), s (step), c (continue), l (list), p (print)

**Using logging**

.. code-block:: python

   import logging
   logging.basicConfig(level=logging.DEBUG)
   logger = logging.getLogger(__name__)
   logger.debug("Debug message")

**Using Python Debugger in IDE**

Most IDEs support debugging:

- PyCharm: Run > Debug
- VS Code: Run > Start Debugging
- Jupyter: Use ``%debug`` magic

Performance Profiling
~~~~~~~~~~~~~~~~~~~~~

**Using cProfile**

.. code-block:: python

   import cProfile
   import pstats

   profiler = cProfile.Profile()
   profiler.enable()

   # Code to profile here

   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative')
   stats.print_stats(10)

**Using Memory Profiler**

.. code-block:: bash

   pip install memory-profiler
   python -m memory_profiler script.py

Release Process
~~~~~~~~~~~~~~~

1. Update version in ``pyproject.toml`` and ``__init__.py``
2. Update ``CHANGELOG.md``
3. Run tests: ``pytest``
4. Build: ``python -m build``
5. Tag release: ``git tag v0.0.2``
6. Push to PyPI: ``twine upload dist/*``

Security Considerations
~~~~~~~~~~~~~~~~~~~~~~~

- No hardcoded secrets
- Use environment variables for credentials
- Validate user inputs
- Keep dependencies updated
- Report vulnerabilities responsibly

.. note::

   See :doc:`/developer-guide/testing` for comprehensive testing guidelines.

Next Steps
~~~~~~~~~~

- Review :doc:`/developer-guide/testing` for testing
- Check :doc:`/developer-guide/contributing` for contribution process
- See :doc:`/api/modules` for current API
