Frequently Asked Questions (FAQ)
================================

General Questions
~~~~~~~~~~~~~~~~~

**What is repo-sapiens?**

repo-sapiens is an intelligent repository automation and management tool. Like *Homo sapiens* evolved beyond their predecessors, repo-sapiens brings intelligent, evolved repository automation capabilities.

**Is it ready for production use?**

Version 0.0.2 is a placeholder release. The complete feature set will be available in upcoming releases. Current version provides basic functionality for testing the distribution workflow.

**How much does it cost?**

repo-sapiens is free and open source under the MIT License.

**Can I use it commercially?**

Yes! The MIT License permits commercial use, modification, and distribution. See the LICENSE file for details.

**What does the name mean?**

repo-sapiens is inspired by *Homo sapiens* (wise human). Just as *Homo sapiens* evolved beyond their predecessors with advanced intelligence, repo-sapiens brings evolved, intelligent repository automation.

Installation & Setup
~~~~~~~~~~~~~~~~~~~~

**What are the system requirements?**

- Python 3.8 or higher
- pip or another package manager
- No external system dependencies for basic functionality

**How do I install repo-sapiens?**

.. code-block:: bash

   pip install repo-sapiens

See :doc:`/installation` for detailed instructions.

**Can I install from source?**

Yes:

.. code-block:: bash

   git clone https://github.com/savorywatt/repo-sapiens.git
   cd repo-sapiens
   pip install -e .

See :doc:`/developer-guide/development` for more details.

**I get an ImportError when trying to import. What's wrong?**

Make sure the package is installed:

.. code-block:: bash

   pip install repo-sapiens

Or in development:

.. code-block:: bash

   pip install -e .

**Can I use it in a virtual environment?**

Yes, and it's recommended! See :doc:`/installation` for instructions.

**Can I use it in a Docker container?**

Yes, install it like you would normally:

.. code-block:: dockerfile

   FROM python:3.9
   RUN pip install repo-sapiens
   # ... rest of your Dockerfile

Usage Questions
~~~~~~~~~~~~~~~

**What can I do with repo-sapiens right now (v0.0.2)?**

The current placeholder release provides:

- Basic greeting functions (greet, get_greeting)
- Full type hints and documentation
- Package structure for future features

See :doc:`/api/core` for available functions.

**When will feature X be available?**

Check the :doc:`/release-notes` for planned features and timelines. Follow the GitHub repository for announcements.

**How do I use repo-sapiens with my project?**

See :doc:`/user-guide/workflows` for usage patterns and examples.

**Can I use it with FastAPI/Flask/Django?**

Yes! See the workflow examples in :doc:`/user-guide/workflows` for integration patterns.

**How do I configure repo-sapiens?**

See :doc:`/user-guide/configuration` for configuration options.

API & Development
~~~~~~~~~~~~~~~~~

**Where is the API documentation?**

See :doc:`/api/modules` for complete API reference.

**How do I contribute?**

See :doc:`/developer-guide/contributing` for guidelines and instructions.

**How do I report a bug?**

1. Check existing issues: https://github.com/savorywatt/repo-sapiens/issues
2. Click "New Issue" and choose "Bug Report"
3. Provide:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Python version and OS
   - Error message/traceback

**How do I request a feature?**

1. Check existing issues
2. Click "New Issue" and choose "Feature Request"
3. Describe:
   - What you want to do
   - Why you need it
   - How it should work

**Is there a roadmap?**

Check the GitHub repository for issues labeled "roadmap" and project plans.

**How are decisions made about the project?**

Currently, decisions are made by the maintainer. As the project grows, we'll establish a governance model.

**Can I fork the project?**

Yes! The MIT License allows forking and modifications.

**How do I stay updated?**

- Watch the GitHub repository
- Follow release announcements
- Check this documentation

Type Hints & IDE Support
~~~~~~~~~~~~~~~~~~~~~~~~

**Does repo-sapiens support type hints?**

Yes! All public APIs have full type hints. See :doc:`/api/core` for examples.

**Does it work with mypy?**

Yes:

.. code-block:: bash

   mypy your_script.py

**Does it work with PyCharm?**

Yes! Full IDE support with autocomplete and type checking.

**Does it work with VS Code?**

Yes! Install the Python and Pylance extensions.

Testing & Quality
~~~~~~~~~~~~~~~~~

**How do I run tests?**

.. code-block:: bash

   pip install -e ".[dev]"
   pytest

See :doc:`/developer-guide/testing` for details.

**What is the test coverage?**

See :doc:`/developer-guide/testing` for coverage targets and how to check coverage.

**Can I contribute tests?**

Yes, please! See :doc:`/developer-guide/contributing` for guidelines.

Troubleshooting
~~~~~~~~~~~~~~~

**The documentation won't build**

Make sure Sphinx is installed:

.. code-block:: bash

   pip install sphinx sphinx-rtd-theme

Then rebuild:

.. code-block:: bash

   cd docs
   make clean html

**Tests fail with import errors**

Install in editable mode:

.. code-block:: bash

   pip install -e .

**Permission denied errors on macOS/Linux**

Use a virtual environment instead of installing globally:

.. code-block:: bash

   python -m venv venv
   source venv/bin/activate
   pip install repo-sapiens

**My pull request hasn't been reviewed**

- PRs are reviewed in order received
- Complex PRs may take longer
- Be patient and follow up if needed

Getting Help
~~~~~~~~~~~~

**How do I get help?**

- Read the :doc:`/documentation`
- Search existing GitHub issues
- Open a new GitHub issue with your question
- Check this FAQ

**Where are discussions held?**

Currently on GitHub Issues. Community discussions features may be added in the future.

**Is there a chat community?**

Not yet. Follow the GitHub repository for announcements about community channels.

**Can I contact the maintainer directly?**

Through GitHub profile or by opening an issue. Email contact coming soon.

Still Have Questions?
~~~~~~~~~~~~~~~~~~~~~

If your question isn't answered here:

1. Search the documentation using the search box at the top
2. Check `GitHub Issues <https://github.com/savorywatt/repo-sapiens/issues>`_
3. `Open a new issue with your question <https://github.com/savorywatt/repo-sapiens/issues/new>`_

We're here to help!

.. note::

   This FAQ will expand as common questions arise. Suggestions for additional FAQs are welcome!
