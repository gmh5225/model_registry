import logging
import sys
import os # Added for path operations
from pathlib import Path # Added for path operations

# Determine the project root. Assumes logger.py is in src/model_registry.
# Adjust if the structure is different.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_PATH = LOG_DIR / "app.log"

# Determine if we are running in a GitHub Actions environment
# IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

def setup_logging(level=logging.INFO):
    """Set up console and file logger."""
    
    # Create logs directory if it doesn't exist
    if not LOG_DIR.exists():
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Fallback to console logging if directory creation fails
            # Using a basic print here as logger might not be fully set up
            print(f"Warning: Could not create log directory {LOG_DIR}. Error: {e}. File logging will be disabled.", file=sys.stderr)
            # Basic console setup as fallback
            logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', stream=sys.stdout)
            return logging.getLogger("model_registry") # Return a configured logger

    logger = logging.getLogger("model_registry")
    logger.setLevel(level)

    # Prevent duplicate handlers if setup_logging is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create formatter
    # Basic format for local, more detailed for GHA if needed later
    # if IS_GITHUB_ACTIONS:
    # formatter = logging.Formatter(
    #     "::%(levelname)s file=%(filename)s line=%(lineno)d func=%(funcName)s :: %(message)s"
    # )
    # else:
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Create console handler
    ch = logging.StreamHandler(sys.stdout) # Stream to stdout
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Create file handler
    try:
        fh = logging.FileHandler(LOG_FILE_PATH)
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        # If file handler setup fails, log a warning to the console handler
        logger.warning(f"Could not set up file handler at {LOG_FILE_PATH}. Error: {e}. Logging to console only.")

    return logger

# Initialize logger when this module is imported
# logger = setup_logging() 