import os
import sys
import shutil
from pathlib import Path

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
html_static_path = ['_static', 'screenshots']

master_doc = 'index'

# Copy screenshots to _static during build
screenshots_src = Path(__file__).parent / 'screenshots'
screenshots_dst = Path(__file__).parent / '_static' / 'screenshots'
if screenshots_src.exists():
    shutil.copytree(str(screenshots_src), str(screenshots_dst), dirs_exist_ok=True)
