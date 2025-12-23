# repo-sapiens Documentation

This directory contains the Sphinx-based documentation for repo-sapiens.

## Building Documentation

### Prerequisites

Install documentation dependencies:

```bash
pip install -r requirements.txt
```

Or install the full development package:

```bash
pip install -e "..[dev]"
```

### Build HTML Documentation

From the `docs/` directory:

```bash
# Clean previous builds
make clean

# Build HTML documentation
make html
```

The built documentation will be in `_build/html/index.html`.

### View Documentation Locally

**Option 1: Using Python's built-in HTTP server**

```bash
cd _build/html
python -m http.server 8000
```

Then visit: http://localhost:8000

**Option 2: Using live reload (sphinx-autobuild)**

```bash
sphinx-autobuild source _build/html
```

Then visit: http://localhost:8000

Changes to source files will automatically rebuild the documentation.

### Build Other Formats

```bash
# PDF (requires LaTeX)
make latexpdf

# Single HTML file
make singlehtml

# Epub
make epub

# Man pages
make man
```

## Documentation Structure

```
source/
├── conf.py                  # Sphinx configuration
├── index.rst               # Documentation home page
├── getting-started.rst     # Getting started guide
├── installation.rst        # Installation guide
├── user-guide/
│   ├── overview.rst       # Feature overview
│   ├── configuration.rst  # Configuration guide
│   └── workflows.rst      # Usage patterns
├── api/
│   ├── core.rst           # Core API reference
│   └── modules.rst        # Module index
├── developer-guide/
│   ├── contributing.rst   # Contributing guidelines
│   ├── development.rst    # Development guide
│   └── testing.rst        # Testing guide
├── release-notes.rst       # Release notes
├── faq.rst                # Frequently asked questions
└── _static/               # Static assets
    └── custom.css         # Custom CSS
```

## Writing Documentation

### Adding New Pages

1. Create `.rst` file in appropriate directory
2. Add it to the toctree in `index.rst` or parent document
3. Use reStructuredText syntax (see below)

### reStructuredText Syntax

Key syntax for documentation:

```rst
# Heading 1 (page title)
# Use = above and below

Heading 2
=========
Use = below

Heading 3
---------
Use - below

Heading 4
~~~~~~~~~
Use ~ below

Inline Code
-----------
Use backticks: ``code``

Code Blocks
-----------
Use double colon and indent::

    code block
    indented

Or use code-block directive:

.. code-block:: python

    def hello():
        print("Hello")

Cross References
----------------
:ref:`label-name`
:doc:`/path/to/page`

Lists
-----
* Item 1
* Item 2
  * Nested
  * Items

1. Numbered
2. Items

Emphasis
--------
*italics* or _italics_
**bold** or __bold__
``inline code``

Links
-----
`Link text <http://example.com>`_

Tables
------
+-------+-------+
| Head1 | Head2 |
+=======+=======+
| Row1  | Data  |
+-------+-------+

Admonitions
-----------
.. note::
   Note content

.. warning::
   Warning content

.. caution::
   Caution content

.. tip::
   Tip content

.. important::
   Important content

.. danger::
   Danger content

Code Directives
---------------
.. code-block:: python
   :linenos:

   # Python code with line numbers

.. doctest::

   >>> 1 + 1
   2

.. highlight:: python

Auto-generated Content
----------------------
.. automodule:: module_name
   :members:

.. autoclass:: ClassName
   :members:
   :undoc-members:

.. autofunction:: function_name

.. autosummary::
   :toctree: _autosummary

   module.Class
   module.function
```

### Adding API Documentation

Use autodoc directives:

```rst
Core Module
===========

.. automodule:: repo_sapiens.core
   :members:
   :undoc-members:
   :show-inheritance:
```

### Documentation Best Practices

1. **Clear Titles**: Use descriptive, action-oriented titles
2. **Structure**: Start with overview, then examples, then details
3. **Code Examples**: Provide runnable examples
4. **Cross-linking**: Use ``:ref:`` and ``:doc:`` for internal links
5. **External Links**: Include relevant external resource links
6. **Consistency**: Follow existing documentation style
7. **Completeness**: Document all public APIs
8. **Clarity**: Explain the "why" not just the "what"

## Sphinx Configuration

Key configuration in `conf.py`:

- **Theme**: ReadTheDocs theme for professional appearance
- **Extensions**: autodoc, napoleon, viewcode, doctest
- **Napoleon**: Parses Google-style docstrings
- **Autosummary**: Generates API summaries automatically
- **Viewcode**: Links to source code in docs

## Theme Customization

Custom CSS is in `_static/custom.css`. Modify this file to change:

- Colors
- Fonts
- Layout
- Styling

## Hosting Documentation

### ReadTheDocs

1. Go to https://readthedocs.org
2. Connect your GitHub repository
3. Select the repo-sapiens repository
4. Documentation will build automatically on pushes

### GitHub Pages

1. Build locally: `make html`
2. Commit `_build/html/` to `gh-pages` branch
3. Enable GitHub Pages in repository settings

### Custom Domain

1. Configure hosting service (ReadTheDocs, GitHub Pages, etc.)
2. Point DNS to hosting service
3. Add domain in hosting configuration

## Troubleshooting

### Sphinx Not Found

Install Sphinx:

```bash
pip install sphinx sphinx-rtd-theme
```

### Import Errors in autodoc

Make sure package is installed:

```bash
pip install -e .
```

### Build Errors

Clean and rebuild:

```bash
make clean
make html
```

Check for errors in output.

### Links Not Working

Verify reference labels exist:

```bash
# In referenced document
.. _my-label:

My Section
==========
```

Then reference:

```rst
See :ref:`my-label`
```

## More Information

- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [reStructuredText Primer](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html)
- [ReadTheDocs Theme](https://sphinx-rtd-theme.readthedocs.io/)
- [Napoleon Extension](https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html)

## Contributing Documentation

See the main contributing guide for how to improve documentation.
