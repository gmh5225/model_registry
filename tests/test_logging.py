#!/usr/bin/env python
"""Test script to verify logging is working correctly."""

from model_registry.logger import setup_logging

# Set up logging
logger = setup_logging()

# Log messages at different levels
logger.debug("This is a DEBUG message")
logger.info("This is an INFO message")
logger.warning("This is a WARNING message")
logger.error("This is an ERROR message")
logger.critical("This is a CRITICAL message")

print("\nLogging test complete. Check logs/app.log to see if messages were written to file.") 