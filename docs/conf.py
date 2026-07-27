"""Sphinx configuration for the glpi-python-client documentation."""

from __future__ import annotations

from datetime import date
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    from tomllib import loads as toml_loads
except ModuleNotFoundError:
    from tomli import loads as toml_loads


def _read_project_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject_data = toml_loads(pyproject_path.read_text(encoding="utf-8"))
    return str(pyproject_data["project"]["version"])


project = "glpi-python-client"
author = "glpi-python-client contributors"
copyright = f"{date.today().year}, {author}"

try:
    release = version("glpi-python-client")
except PackageNotFoundError:
    release = _read_project_version()

version = release

extensions = [
    "numpydoc",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = "glpi-python-client documentation"

add_module_names = False
autoclass_content = "both"
autodoc_class_signature = "mixed"
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "special-members": "__enter__, __exit__",
}
autodoc_typehints = "description"
autosummary_generate = True

numpydoc_class_members_toctree = False
numpydoc_show_class_members = True
numpydoc_xref_param_type = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
