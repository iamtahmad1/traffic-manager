# src/logger/__init__.py
# This file makes the logger folder a Python package
# It also exports the functions we want other files to use
# Note: We named it 'logger' instead of 'logging' to avoid conflict with Python's built-in logging module

# Import our logging setup functions
# The dot (.) means "from the current package"
# So .logging means "from the logging.py file in this same folder"
from .logging import setup_logging, get_logger

# __all__ is a special list that defines what gets exported
# When someone does "from logger import *", only things in __all__ are imported
# This is a best practice - it makes it clear what the package provides
__all__ = [
    "setup_logging",
    "get_logger",
]
