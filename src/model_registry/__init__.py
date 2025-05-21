from .logger import setup_logging

# Initialize the logger for the model_registry package
logger = setup_logging()

__all__ = ["logger"] # Optional: define what `from model_registry import *` imports 