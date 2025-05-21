from pathlib import Path
from typing import List
import json
from ..schemas import ModelEntry
from logging import getLogger

logger = getLogger(__name__)

def load_existing_models(path: Path) -> List[ModelEntry]:
    """Loads existing models from the JSON file."""
    if not path.exists():
        return []
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        # Validate with Pydantic, skip invalid entries
        valid_models = []
        for item in data:
            try:
                valid_models.append(ModelEntry(**item))
            except Exception as e: # Catch Pydantic ValidationError specifically if possible
                logger.warning(f"Skipping invalid model data in {path}: {item}. Error: {e}")
        
        logger.info(f"Loaded {len(valid_models)} models from {path}.")
        return valid_models
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {path}. Starting with an empty list.")
        return []
    except Exception as e:
        logger.error(f"Error loading models from {path}: {e}. Starting with an empty list.")
        return []
    
def save_models(path: Path, models: List[ModelEntry]) -> None:
    """Saves models to the JSON file."""
    try:
        models_dict = [model.model_dump(mode='json') for model in models]
        with open(path, 'w') as f:
            json.dump(models_dict, f, indent=2)
        logger.info(f"Successfully saved {len(models)} models to {path}")
    except Exception as e:
        logger.error(f"Error saving models to {path}: {e}")