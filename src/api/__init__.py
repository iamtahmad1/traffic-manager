# src/api/__init__.py
# This file makes the api folder a Python package
# It exports the Flask application factory

from .app import create_app

__all__ = [
    "create_app",
]
