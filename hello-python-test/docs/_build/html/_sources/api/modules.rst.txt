Module Index
=============

Complete Module Reference
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autosummary::
   :toctree: generated
   :maxdepth: 2
   :template: module.rst

   repo_sapiens
   repo_sapiens.core

Package Structure
~~~~~~~~~~~~~~~~~

.. code-block:: text

   repo_sapiens/
   ├── __init__.py      - Package initialization and exports
   └── core.py          - Core functionality

Main Package
~~~~~~~~~~~~

.. automodule:: repo_sapiens
   :members:
   :undoc-members:
   :show-inheritance:

**Exports:**

- ``greet`` - Print a greeting message
- ``get_greeting`` - Generate a greeting string
- ``__version__`` - Package version

Core Module
~~~~~~~~~~~

.. automodule:: repo_sapiens.core
   :members:
   :undoc-members:
   :show-inheritance:

**Functions:**

- ``greet(name=None)`` - Print a greeting
- ``get_greeting(name="World")`` - Get greeting as string

Future Modules
~~~~~~~~~~~~~~

When the full release is available, this index will include:

- ``repo_sapiens.config`` - Configuration management
- ``repo_sapiens.credentials`` - Credential handling
- ``repo_sapiens.git`` - Git operations
- ``repo_sapiens.rendering`` - Template rendering
- ``repo_sapiens.cli`` - Command-line interface
- ``repo_sapiens.models`` - Domain models
- And more...

API Documentation
~~~~~~~~~~~~~~~~~

- :doc:`/api/core` - Core module API reference
- :doc:`/user-guide/overview` - Feature overview

Search
~~~~~~

Use the search function (top of page) to find specific API elements:

- Functions: Search for ``def function_name``
- Classes: Search for ``class ClassName``
- Methods: Search for ``method_name``
- Parameters: Search for parameter names

Examples
~~~~~~~~

Finding API elements:

1. **By name**: Search "greet" to find greeting functions
2. **By module**: Use sidebar navigation under "API Reference"
3. **By type**: Look in appropriate module sections

.. note::

   This module index will be significantly expanded when the full feature set is released.
