"""Compatibility shim for legacy tooling.

Project metadata lives in pyproject.toml. Keeping this tiny setup.py lets older
pip/setuptools flows delegate cleanly without duplicating metadata.
"""

from setuptools import setup

setup()
