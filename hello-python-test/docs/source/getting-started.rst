Getting Started
===============

Installation
~~~~~~~~~~~~

The easiest way to install **repo-sapiens** is using pip:

.. code-block:: bash

   pip install repo-sapiens

For development installation from source:

.. code-block:: bash

   git clone https://github.com/savorywatt/repo-sapiens.git
   cd repo-sapiens
   pip install -e .

For development with testing dependencies:

.. code-block:: bash

   pip install -e ".[dev]"

Verification
~~~~~~~~~~~~

Verify your installation by running:

.. code-block:: bash

   python -c "from repo_sapiens import __version__; print(__version__)"

You should see the version number printed.

Your First Program
~~~~~~~~~~~~~~~~~~

Create a new file ``hello.py``:

.. code-block:: python

   from repo_sapiens import greet, get_greeting

   # Print a greeting
   greet()

   # Or get a greeting string
   message = get_greeting("Python Developer")
   print(message)

Run it:

.. code-block:: bash

   python hello.py

Expected output:

.. code-block:: text

   Hello, World!
   Hello, Python Developer!

What's Next?
~~~~~~~~~~~~

- Read the :doc:`user-guide/overview` for an overview of core features
- Check out the :doc:`api/core` for API reference
- Explore :doc:`user-guide/workflows` for common use cases
- Review the :doc:`developer-guide/contributing` to contribute back

System Requirements
~~~~~~~~~~~~~~~~~~~~

- **Python**: 3.8 or higher (3.9+ recommended)
- **OS**: Linux, macOS, Windows
- **Dependencies**: None for basic functionality (see ``pyproject.toml`` for optional dependencies)

.. note::

   repo-sapiens is actively under development. The complete feature set will be available in upcoming releases.

Getting Help
~~~~~~~~~~~~

- **Documentation**: You're reading it! Check the sidebar for more
- **GitHub Issues**: `Report bugs or request features <https://github.com/savorywatt/repo-sapiens/issues>`_
- **Discussions**: Join community discussions on the GitHub repository

Troubleshooting
~~~~~~~~~~~~~~~

**ImportError: cannot import name 'greet'**

Make sure you have the correct version installed:

.. code-block:: bash

   pip install --upgrade repo-sapiens

**Version mismatch**

Some features may depend on specific Python versions. Check :ref:`genindex` for compatibility information.
