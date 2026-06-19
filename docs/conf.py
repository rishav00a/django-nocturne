import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'django-nocturne'
copyright = '2026, Rishav'
author = 'Rishav'
release = '0.1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
]

html_theme = 'sphinx_rtd_theme'
exclude_patterns = ['_build']

master_doc = 'index'
