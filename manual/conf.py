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
    "ablog", 
    "myst_parser",
    "sphinx_favicon",
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

favicons = [
    "favicon.svg",
]

# -- Extension configuration -------------------------------------------------

pytketdoc_base = "https://tket.quantinuum.com/api-docs/"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "pytket": (pytketdoc_base, None),
}

# ----- ablog config settings -----
ablog_website = "_website"

ablog_builder = "dirhtml"

blog_path = "blog"
blog_baseurl = "https://tket.quantinuum.com/blog/"
blog_title = "TKET Developer Blog"

blog_authors = {
    "Callum Macpherson": ("Callum Macpherson", "https://github.com/CalMacCQ"),
}

blog_post_pattern = ["posts/*.rst", "posts/*.md"]

blog_feed_archives = True
blog_feed_fulltext = True

blog_post_pattern = "blog/*/*"

# List of Sphinx extensions used
extensions = ["ablog", "myst_parser", "sphinx_copybutton", "sphinx_favicon"]

# ----- MyST parser config -----

myst_enable_extensions = ["dollarmath", "html_image", "attrs_inline"]

myst_update_mathjax = False

suppress_warnings = ["myst.xref_missing"]

# Exclude README from blog build
exclude_patterns = ["README.md"]
