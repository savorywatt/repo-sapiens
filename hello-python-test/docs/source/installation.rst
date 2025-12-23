Installation Guide
===================

Official Release (PyPI)
~~~~~~~~~~~~~~~~~~~~~~~

The official release is available on PyPI:

.. code-block:: bash

   pip install repo-sapiens

This installs the latest stable version.

Specifying a Version
~~~~~~~~~~~~~~~~~~~~~

To install a specific version:

.. code-block:: bash

   pip install repo-sapiens==0.0.2

Or to install a version matching a pattern:

.. code-block:: bash

   pip install "repo-sapiens>=0.0.2,<1.0"

From Source
~~~~~~~~~~~

To install the latest development version from source:

.. code-block:: bash

   git clone https://github.com/savorywatt/repo-sapiens.git
   cd repo-sapiens
   pip install -e .

With Development Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For development work with testing and documentation tools:

.. code-block:: bash

   pip install -e ".[dev]"

This installs the package along with development dependencies for running tests, building documentation, and other development activities.

Verifying Installation
~~~~~~~~~~~~~~~~~~~~~~

Check that the installation was successful:

.. code-block:: bash

   python -c "import repo_sapiens; print(repo_sapiens.__version__)"

Or in Python:

.. code-block:: python

   >>> import repo_sapiens
   >>> repo_sapiens.__version__
   '0.0.2'

Virtual Environment (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It's best practice to install Python packages in a virtual environment:

.. code-block:: bash

   # Create a virtual environment
   python -m venv venv

   # Activate it
   # On Linux/macOS:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate

   # Install repo-sapiens
   pip install repo-sapiens

Uninstalling
~~~~~~~~~~~~

To remove repo-sapiens:

.. code-block:: bash

   pip uninstall repo-sapiens

System Requirements
~~~~~~~~~~~~~~~~~~~

- **Python**: 3.8 or higher
- **pip**: 19.0 or higher (for modern dependency resolution)
- **No external system dependencies** are required for basic functionality

Supported Python Versions
~~~~~~~~~~~~~~~~~~~~~~~~~

repo-sapiens is tested and supported on:

- Python 3.8
- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12

Troubleshooting
~~~~~~~~~~~~~~~

**"pip: command not found"**

Make sure pip is installed. On some systems, use ``python -m pip`` instead:

.. code-block:: bash

   python -m pip install repo-sapiens

**"Permission denied"**

If you get permission errors, use the ``--user`` flag:

.. code-block:: bash

   pip install --user repo-sapiens

Or better yet, use a virtual environment as shown above.

**ModuleNotFoundError**

If Python can't find the repo_sapiens module after installation:

1. Verify the installation: ``pip show repo-sapiens``
2. Ensure you're using the correct Python interpreter
3. Try reinstalling: ``pip install --force-reinstall repo-sapiens``

Next Steps
~~~~~~~~~~

Once installed, head to :doc:`getting-started` to write your first program!
