Core Module API
===============

The ``repo_sapiens.core`` module provides foundational functionality.

Module Reference
~~~~~~~~~~~~~~~~

.. automodule:: repo_sapiens.core
   :members:
   :undoc-members:
   :show-inheritance:

Functions
~~~~~~~~~

greet
-----

.. autofunction:: repo_sapiens.core.greet

Print a greeting message to stdout.

**Parameters:**

- ``name`` (str, optional): The name to include in the greeting. If not provided, defaults to "World".

**Returns:**

- ``None``

**Example:**

.. code-block:: python

   from repo_sapiens import greet

   greet()  # Output: Hello, World!
   greet("Alice")  # Output: Hello, Alice!

get_greeting
------------

.. autofunction:: repo_sapiens.core.get_greeting

Generate a greeting message as a string.

**Parameters:**

- ``name`` (str): The name to include in the greeting. Defaults to "World".

**Returns:**

- ``str``: The greeting message.

**Example:**

.. code-block:: python

   from repo_sapiens import get_greeting

   msg = get_greeting()  # Returns: "Hello, World!"
   msg = get_greeting("Bob")  # Returns: "Hello, Bob!"

Full Module Documentation
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: repo_sapiens.core
   :members:
   :private-members:
   :special-members:
   :undoc-members:
   :show-inheritance:

Type Hints
~~~~~~~~~~

All functions are fully type-hinted for IDE support:

.. code-block:: python

   from typing import Optional

   def greet(name: Optional[str] = None) -> None: ...
   def get_greeting(name: str = "World") -> str: ...

See Also
~~~~~~~~

- :doc:`/user-guide/overview` for an overview of features
- :doc:`/user-guide/workflows` for usage patterns
- :doc:`/developer-guide/development` for development information
