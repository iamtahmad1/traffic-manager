# src/logger/logging.py
# This file sets up centralized logging configuration for our application
# Logging is like keeping a diary of what the code is doing
# By centralizing it here, we can change logging settings in one place
# Note: We use Python's built-in 'logging' module here, which is why we named our folder 'logger'

import logging
import sys
from typing import Optional

# Logging levels (from least to most important):
# DEBUG: Very detailed information, usually only of interest when diagnosing problems
# INFO: Confirmation that things are working as expected
# WARNING: Something unexpected happened, but the software is still working
# ERROR: A serious problem occurred, some function failed
# CRITICAL: A serious error occurred, the program itself may be unable to continue


class CorrelationIDFilter(logging.Filter):
    """
    Logging filter that adds correlation ID to all log records.
    
    This filter automatically includes the correlation ID in every log message,
    making it easy to trace requests through the system.
    """
    
    def filter(self, record):
        """
        Add correlation ID to log record if available.
        
        Args:
            record: Log record to modify
        
        Returns:
            True (always allow the log record)
        """
        try:
            from tracking.correlation import get_correlation_id
            correlation_id = get_correlation_id()
            if correlation_id:
                record.correlation_id = correlation_id
            else:
                record.correlation_id = "-"
        except (ImportError, Exception):
            # If tracking module is not available or there's an error, use "-"
            record.correlation_id = "-"
        
        return True


def setup_logging(level: Optional[str] = None):
    """
    Configure logging for the entire application.
    
    This function sets up how logs are formatted and where they go.
    We call this once at the start of the application.
    
    Args:
        level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               If None, uses level from centralized config
    """
    # Try to import config, but don't fail if it's not available
    # This allows the logger to be used even if config isn't set up yet
    try:
        from config import settings
        # Get log level from centralized config (preferred)
        log_level = level or settings.app.log_level
    except ImportError:
        # Fallback to parameter or default if config not available
        log_level = level or "INFO"
    
    # Convert string level to logging constant
    # logging.INFO, logging.DEBUG, etc. are numbers that Python uses internally
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create a custom formatter that includes correlation ID
    # Format explanation:
    # %(asctime)s: Timestamp (when the log was created)
    # %(correlation_id)s: Correlation ID for request tracking (added by filter)
    # %(name)s: Name of the logger (usually the module/file name)
    # %(levelname)s: Log level (INFO, WARNING, ERROR, etc.)
    # %(message)s: The actual log message
    formatter = logging.Formatter(
        '%(asctime)s - [%(correlation_id)s] - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create a handler for console output
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # Add correlation ID filter to the handler
    handler.addFilter(CorrelationIDFilter())
    
    # Configure the root logger (the main logger that all others inherit from)
    # basicConfig() sets up the default logging behavior
    logging.basicConfig(
        level=numeric_level,  # Only show messages at this level or higher
        handlers=[handler]
        # We could add more handlers here, like:
        # - FileHandler: write logs to a file
        # - RotatingFileHandler: write to files that rotate when they get too big
    )

def get_logger(name: Optional[str] = None):
    """
    Get a logger instance for a specific module.
    
    Each file should create its own logger using this function.
    The logger name helps us know which file the log message came from.
    
    Args:
        name: Name of the logger (usually __name__ from the calling module)
              If None, returns the root logger
    
    Returns:
        A logger object that can be used to write log messages
    """
    return logging.getLogger(name)

# Automatically set up logging when this module is imported
# This means logging is configured as soon as we import from this module
setup_logging()
