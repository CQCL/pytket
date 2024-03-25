# -*- coding: utf-8 -*-

# Configuration file for the Sphinx documentation builder.
# See https://www.sphinx-doc.org/en/master/usage/configuration.html

copyright = "2020-2024, Quantinuum"
author = "Quantinuum"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "jupyter_sphinx",
    "sphinx_copybutton",
    "sphinx.ext.autosectionlabel",
]

html_theme = "sphinx_book_theme"

html_title = "pytket user manual"

html_theme_options = {
    "repository_url": "https://github.com/CQCL/tket",
    "use_repository_button": True,
    "navigation_with_keys": True,
    "use_issues_button": True,
    "logo": {
        "image_light": "_static/Quantinuum_logo_black.png",
        "image_dark": "_static/Quantinuum_logo_white.png",
    },
}

html_static_path = ["_static"]

html_css_files = ["custom.css"]

# -- Extension configuration -------------------------------------------------

pytketdoc_base = "https://tket.quantinuum.com/api-docs/"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "pytket": (pytketdoc_base, None),
    "qiskit": ("https://docs.quantum.ibm.com/api/qiskit", None),
    "pytket-qiskit": ("https://tket.quantinuum.com/extensions/pytket-qiskit/", None),
    "pytket-quantinuum": (
        "https://tket.quantinuum.com/extensions/pytket-quantinuum/",
        None,
    ),
}
