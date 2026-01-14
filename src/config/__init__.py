# src/config/__init__.py
# This file makes the config folder a Python package
# It exports the settings object that other modules can import

from .settings import settings

__all__ = [
    "settings",
]
