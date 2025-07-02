import logging
import sys
from typing import Optional


def setup_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Set up a logger with the specified name and level.

    Args:
        name: The name of the logger
        level: The logging level (defaults to INFO)

    Returns:
        logging.Logger: The configured logger
    """
    logger = logging.getLogger(name)

    if level is None:
        level = logging.INFO

    logger.setLevel(level)

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)

    return logger
