Contributing Guide
==================

We welcome contributions to repo-sapiens! This guide explains how to get started.

Getting Started with Development
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Fork and Clone**

1. Fork the repository on GitHub: https://github.com/savorywatt/repo-sapiens
2. Clone your fork locally:

   .. code-block:: bash

      git clone https://github.com/YOUR-USERNAME/repo-sapiens.git
      cd repo-sapiens

**Set Up Development Environment**

1. Create a virtual environment:

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows: venv\Scripts\activate

2. Install development dependencies:

   .. code-block:: bash

      pip install -e ".[dev]"

3. Verify installation:

   .. code-block:: bash

      python -c "import repo_sapiens; print(repo_sapiens.__version__)"

Making Changes
~~~~~~~~~~~~~~

**Create a Branch**

.. code-block:: bash

   git checkout -b feature/your-feature-name
   # or for bug fixes:
   git checkout -b fix/bug-description

**Code Style**

Follow these guidelines:

- **PEP 8**: Use black for formatting
- **Type Hints**: Add type hints to all functions
- **Docstrings**: Use Google-style docstrings
- **Comments**: Only for "why", not "what"

Example:

.. code-block:: python

   from typing import Optional

   def process_data(input_value: str) -> Optional[str]:
       """
       Process input data and return result.

       Args:
           input_value: The input string to process

       Returns:
           The processed result, or None if processing failed
       """
       if not input_value:
           return None
       return input_value.strip().upper()

**Testing**

Write tests for your changes:

.. code-block:: bash

   # Run tests
   pytest

   # Run with coverage
   pytest --cov=repo_sapiens

   # Run specific test
   pytest tests/test_core.py

See :doc:`/developer-guide/testing` for more information.

**Documentation**

Update documentation for public APIs:

1. Update docstrings in the code
2. Update or create .rst files in ``docs/source/``
3. Test documentation build:

   .. code-block:: bash

      cd docs
      make html

Submitting Changes
~~~~~~~~~~~~~~~~~~

**Commit Messages**

Write clear, descriptive commit messages:

.. code-block:: bash

   git commit -m "feat: Add new feature description"
   git commit -m "fix: Fix bug in core module"
   git commit -m "docs: Update API documentation"
   git commit -m "test: Add tests for feature"

Use conventional commit prefixes:

- ``feat:``: New feature
- ``fix:``: Bug fix
- ``docs:``: Documentation changes
- ``test:``: Test additions/changes
- ``refactor:``: Code refactoring
- ``perf:``: Performance improvements
- ``chore:``: Build, dependencies, etc.

**Create Pull Request**

1. Push to your fork:

   .. code-block:: bash

      git push origin feature/your-feature-name

2. Go to GitHub and click "New Pull Request"
3. Fill out the PR template with:
   - Clear description of changes
   - Related issues (use "Fixes #123")
   - Testing performed
   - Breaking changes (if any)

Contribution Areas
~~~~~~~~~~~~~~~~~~

We're particularly interested in contributions for:

**Development in Progress**

- Repository automation features
- Configuration management
- Git integration
- Template rendering engine
- Credential management system
- CLI implementation

**Always Needed**

- Documentation improvements
- Test coverage expansion
- Bug reports and fixes
- Performance optimizations
- Type hint improvements

Code Review Process
~~~~~~~~~~~~~~~~~~~

1. A maintainer will review your PR
2. You may be asked to make changes
3. Once approved, your PR will be merged
4. Your contribution will be credited in release notes

Reporting Issues
~~~~~~~~~~~~~~~~

Found a bug or have a feature request?

1. Check existing issues: https://github.com/savorywatt/repo-sapiens/issues
2. Click "New Issue"
3. Choose the appropriate template:
   - Bug Report: Include steps to reproduce
   - Feature Request: Describe the use case
4. Provide as much detail as possible

Community Guidelines
~~~~~~~~~~~~~~~~~~~~

- Be respectful and inclusive
- Assume good intentions
- Focus on the code, not the person
- Help others learn and grow
- Report issues constructively

Getting Help
~~~~~~~~~~~~

- **Questions**: Open a GitHub Discussion or Issue
- **Chat**: Check for community channels (coming soon)
- **Docs**: See the full documentation at https://repo-sapiens.readthedocs.io
- **Email**: Contact maintainers via GitHub profile

Becoming a Maintainer
~~~~~~~~~~~~~~~~~~~~~

Regular contributors who demonstrate:

- Consistent quality code
- Good understanding of the project
- Positive community interactions
- Sustained engagement

May be invited to join the maintainers team. Maintainers help with:

- Code review
- Issue triage
- Release management
- Strategic planning

Thank You!
~~~~~~~~~~

Your contributions make repo-sapiens better for everyone. We appreciate your time and effort!

Next Steps
~~~~~~~~~~

- See :doc:`/developer-guide/development` for technical details
- Review :doc:`/developer-guide/testing` for testing guidelines
- Check :doc:`/api/modules` for current API

.. note::

   Thank you for contributing to repo-sapiens! Every contribution counts.
