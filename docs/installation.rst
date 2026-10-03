Installation
============

Requirements
------------

``glpi-python-client`` supports Python 3.11 and newer. Runtime dependencies are installed
from the package metadata and include ``httpx``, ``tenacity``,
``beautifulsoup4``, ``lxml``, and ``pydantic``, plus the libraries the
rich-text converter is built on: ``markdownify``, ``mdformat``,
``mdformat-tables`` and ``markdown-it-py`` to read, and ``cmarkgfm`` to
write. The reader overrides private surfaces of ``markdownify`` and
``mdformat``, so those four carry upper bounds; ``pyproject.toml`` gives the
reason for each.

Install from PyPI
-----------------

After the package is published, install it with pip:

.. code-block:: console

   python -m pip install glpi-python-client

Install from Source
-------------------

For local development or testing from a checkout, install the package in
editable mode:

.. code-block:: console

   python -m pip install -e .

Install Development Tools
-------------------------

Development checks use the ``dev`` extra:

.. code-block:: console

   python -m pip install -e .[dev]

Documentation builds use the ``docs`` extra:

.. code-block:: console

   python -m pip install -e .[docs]

Build Documentation Locally
---------------------------

Build the Read the Docs HTML site with Sphinx:

.. code-block:: console

   python -m sphinx -b html docs docs/_build/html

The generated site is written to ``docs/_build/html/index.html``.
