# repo-sapiens Documentation Guide

Complete documentation for repo-sapiens is available in the `docs/` directory and online at [https://repo-sapiens.readthedocs.io](https://repo-sapiens.readthedocs.io).

## Quick Links

### Getting Started
- [Installation Guide](docs/source/installation.rst) - How to install repo-sapiens
- [Getting Started](docs/source/getting-started.rst) - Your first program
- [Quick Start](QUICK_START.txt) - Quick reference

### User Documentation
- [Feature Overview](docs/source/user-guide/overview.rst) - What repo-sapiens provides
- [Configuration Guide](docs/source/user-guide/configuration.rst) - Configuring the tool
- [Workflows & Patterns](docs/source/user-guide/workflows.rst) - Common usage patterns

### API Reference
- [Core Module API](docs/source/api/core.rst) - Complete API reference
- [Module Index](docs/source/api/modules.rst) - All available modules

### Developer Documentation
- [Contributing Guide](docs/source/developer-guide/contributing.rst) - How to contribute
- [Development Guide](docs/source/developer-guide/development.rst) - Development setup
- [Testing Guide](docs/source/developer-guide/testing.rst) - Writing and running tests

### Additional Resources
- [Release Notes](docs/source/release-notes.rst) - What's new in each version
- [FAQ](docs/source/faq.rst) - Frequently asked questions
- [License](LICENSE) - MIT License

## Building Documentation Locally

### Prerequisites

Install documentation dependencies:

```bash
pip install -r docs/requirements.txt
```

Or with the development package:

```bash
pip install -e ".[docs]"
```

### Build HTML Documentation

**Option 1: Using make (recommended)**

```bash
cd docs
make clean html
```

Output is in `docs/_build/html/index.html`

**Option 2: Using shell script**

```bash
cd docs
./build.sh
```

**Option 3: Direct sphinx-build command**

```bash
cd docs
sphinx-build -b html source _build/html
```

### View Documentation Locally

**Option 1: Python HTTP Server**

```bash
cd docs/_build/html
python -m http.server 8000
```

Then visit: http://localhost:8000

**Option 2: Live Reload (sphinx-autobuild)**

```bash
cd docs
pip install sphinx-autobuild
./serve.sh
# or: sphinx-autobuild source _build/html
```

Documentation automatically rebuilds when source files change.

### Other Output Formats

```bash
cd docs

# PDF (requires LaTeX)
make latexpdf

# Single HTML file
make singlehtml

# Epub
make epub

# Man pages
make man

# See all available formats
make help
```

## Documentation Structure

```
docs/
├── Makefile                 # Build commands
├── build.sh                 # Build script
├── serve.sh                 # Live reload server
├── requirements.txt         # Dependencies
├── README.md               # Documentation guide
├── source/
│   ├── conf.py             # Sphinx configuration
│   ├── index.rst           # Home page
│   ├── getting-started.rst
│   ├── installation.rst
│   ├── user-guide/
│   │   ├── overview.rst
│   │   ├── configuration.rst
│   │   └── workflows.rst
│   ├── api/
│   │   ├── core.rst
│   │   └── modules.rst
│   ├── developer-guide/
│   │   ├── contributing.rst
│   │   ├── development.rst
│   │   └── testing.rst
│   ├── release-notes.rst
│   ├── faq.rst
│   ├── _static/
│   │   └── custom.css
│   └── _templates/
│       └── module.rst
└── _build/                 # Generated HTML (after building)
    └── html/
        └── index.html
```

## Writing Documentation

Documentation uses reStructuredText (RST) format. See [RST Primer](http://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html).

### Create New Page

1. Create `.rst` file in appropriate directory:
   - `docs/source/user-guide/` for user docs
   - `docs/source/api/` for API docs
   - `docs/source/developer-guide/` for developer docs

2. Add to table of contents in parent document:

   ```rst
   .. toctree::
      :maxdepth: 2

      user-guide/new-page
   ```

3. Rebuild documentation:

   ```bash
   cd docs
   make clean html
   ```

### Documenting Code

Use Google-style docstrings for automatic API documentation:

```python
def my_function(param: str) -> bool:
    """
    Short description of function.

    Longer description with more details about what
    the function does and how to use it.

    Args:
        param: Description of the parameter

    Returns:
        Description of return value

    Raises:
        ValueError: When something is invalid

    Example:
        >>> my_function("example")
        True
    """
    return True
```

Then use autodoc directive:

```rst
.. autofunction:: module_name.my_function
```

## Online Documentation

The official documentation is hosted on ReadTheDocs:

**URL**: [https://repo-sapiens.readthedocs.io](https://repo-sapiens.readthedocs.io)

Documentation is automatically built from the main branch on every push.

## Hosting on ReadTheDocs

The project uses `.readthedocs.yml` for configuration. To set up on ReadTheDocs:

1. Go to https://readthedocs.org
2. Click "Import a Project"
3. Select the repo-sapiens repository
4. Documentation builds automatically

See `.readthedocs.yml` for build configuration.

## GitHub Actions CI/CD

Documentation is tested on every push via GitHub Actions:

- Builds documentation on Python 3.8, 3.9, 3.10, 3.11, 3.12
- Validates all reStructuredText
- Checks for broken links
- Stores build artifacts

See `.github/workflows/docs.yml` for workflow configuration.

## Sphinx Extensions

The documentation uses these Sphinx extensions:

- **autodoc**: Automatically generate API documentation from docstrings
- **autosummary**: Generate summary tables of documented items
- **napoleon**: Parse Google-style docstrings
- **viewcode**: Link to source code in documentation
- **doctest**: Run code examples as tests
- **intersphinx**: Link to external Python documentation

Configuration is in `docs/source/conf.py`.

## Theme

Uses the [ReadTheDocs Theme](https://sphinx-rtd-theme.readthedocs.io/) for professional appearance.

Customizable options in `conf.py`:
- Header color
- Navigation depth
- Layout options

Custom CSS in `docs/source/_static/custom.css`.

## Troubleshooting

### Sphinx not found

```bash
pip install sphinx sphinx-rtd-theme
```

### Import errors in autodoc

Make sure package is installed:

```bash
pip install -e .
```

### Build fails

Clean and rebuild:

```bash
cd docs
make clean html
```

Check error messages in output.

### Links not working

Verify reference labels exist and are spelled correctly. Use:

```rst
.. _my-label:

My Section
==========
```

Then reference with:

```rst
See :ref:`my-label`
```

## Contributing to Documentation

1. Edit `.rst` files in `docs/source/`
2. Build locally: `cd docs && make clean html`
3. Verify output looks correct
4. Submit pull request

See [Contributing Guide](docs/source/developer-guide/contributing.rst) for more details.

## More Information

- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [reStructuredText Primer](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html)
- [ReadTheDocs Theme Docs](https://sphinx-rtd-theme.readthedocs.io/)
- [Napoleon Extension](https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html)

## Questions?

- Check the [FAQ](docs/source/faq.rst)
- Search existing [GitHub Issues](https://github.com/savorywatt/repo-sapiens/issues)
- Open a new [GitHub Issue](https://github.com/savorywatt/repo-sapiens/issues/new)

---

**Last Updated**: December 2024
