# Documentation Quick Start

## Building Locally (2 minutes)

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Build HTML documentation
cd docs
make clean html

# View in browser
cd _build/html
python -m http.server 8000
# Visit: http://localhost:8000
```

## Live Development (continuous updates)

```bash
pip install sphinx-autobuild

cd docs
sphinx-autobuild source _build/html
# Visit: http://localhost:8000
# Auto-rebuilds on file changes
```

## Deployment to ReadTheDocs

1. Push to GitHub
2. Go to https://readthedocs.org
3. Click "Import a Project"
4. Select repo-sapiens repository
5. Documentation builds automatically

**That's it!** Your docs are live at: `https://repo-sapiens.readthedocs.io`

## Documentation Structure

```
Getting Started        → docs/source/getting-started.rst
Installation          → docs/source/installation.rst

User Guide:
  - Overview          → docs/source/user-guide/overview.rst
  - Configuration     → docs/source/user-guide/configuration.rst
  - Workflows         → docs/source/user-guide/workflows.rst

API Reference:
  - Core Module       → docs/source/api/core.rst
  - Module Index      → docs/source/api/modules.rst

Developer Guide:
  - Contributing      → docs/source/developer-guide/contributing.rst
  - Development       → docs/source/developer-guide/development.rst
  - Testing           → docs/source/developer-guide/testing.rst

Additional:
  - Release Notes     → docs/source/release-notes.rst
  - FAQ              → docs/source/faq.rst
```

## Adding New Pages

1. Create `.rst` file in appropriate directory
2. Add to table of contents in parent file
3. Rebuild: `make clean html`

Example:

```rst
My New Page
===========

Content here using reStructuredText syntax.

.. toctree::

   page-to-include
```

## Useful Commands

```bash
cd docs

# Build HTML
make html

# Clean builds
make clean

# Build PDF (requires LaTeX)
make latexpdf

# Build single HTML file
make singlehtml

# Build ePub
make epub

# Check for broken links
make linkcheck

# See all options
make help
```

## Key Files

- **Configuration**: `docs/source/conf.py`
- **Homepage**: `docs/source/index.rst`
- **Dependencies**: `docs/requirements.txt`
- **This Guide**: `DOCUMENTATION.md` (comprehensive)
- **Summary**: `DOCS_SUMMARY.md` (detailed)

## Common Tasks

### Update API Documentation
Edit docstrings in source code, rebuild docs.

### Add User Guide Page
Create file in `docs/source/user-guide/`, add to toctree.

### Update FAQ
Edit `docs/source/faq.rst`, add Q&A.

### Fix Links
Check `.rst` files for typos in `:ref:` and `:doc:` directives.

### Deploy Changes
Push to main branch, ReadTheDocs rebuilds automatically.

## Troubleshooting

**Sphinx not found**
```bash
pip install sphinx sphinx-rtd-theme
```

**Import errors**
```bash
pip install -e .
```

**Build fails**
```bash
cd docs
make clean html
```

**Links broken**
Use `make linkcheck` to find issues.

## Documentation Links

- **Online**: https://repo-sapiens.readthedocs.io
- **Local**: `docs/_build/html/index.html`
- **Full Guide**: `DOCUMENTATION.md`
- **Detailed Summary**: `DOCS_SUMMARY.md`

## Get Help

1. Check `DOCUMENTATION.md` for comprehensive guide
2. View `DOCS_SUMMARY.md` for detailed information
3. Read `docs/README.md` for writing documentation
4. See `docs/source/faq.rst` for common questions

---

**Status**: Complete and ready to deploy!
