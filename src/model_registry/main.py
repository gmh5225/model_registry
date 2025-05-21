import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

from dotenv import load_dotenv

# Assuming providers are structured as in the project description
# Adjust imports based on actual file structure and class names
from model_registry.providers.openai import OpenAIProvider
# from model_registry.providers.anthropic import AnthropicProvider # Placeholder for when M8 is done
from model_registry.providers.base import Provider
from model_registry.schemas import ModelEntry
from model_registry.logger import setup_logging
from model_registry.utils.utils import load_existing_models, save_models
from .feed import build_atom_feed # Added import

load_dotenv()

# Setup logging
setup_logging(level=logging.DEBUG)
logger = logging.getLogger("model_registry")

# Determine the models.json path based on the current working directory.
# This assumes the script is run from the project's root directory.
WORKSPACE_ROOT = Path.cwd()
MODELS_JSON_PATH = WORKSPACE_ROOT / "models.json"
logger.info(f"Assuming CWD is project root. WORKSPACE_ROOT: {WORKSPACE_ROOT}")
logger.info(f"MODELS_JSON_PATH set to: {MODELS_JSON_PATH}")

# Get the repository URL from an environment variable, with a fallback.
# This URL is used for generating feed and entry IDs in the Atom feed.
REPO_URL = os.environ.get("MODEL_REGISTRY_REPO_URL", "https://your-repo-url-here.com")
logger.info(f"Using REPO_URL: {REPO_URL}")

def fetch_all_models(providers: List[Provider]) -> List[ModelEntry]:
    """Fetches models from all registered providers."""
    all_new_models: List[ModelEntry] = []

    for provider_instance in providers:
        try:
            logger.info(f"Fetching models from {provider_instance.slug}...")
            public_models = provider_instance.public_models()
            if public_models:
                 all_new_models.extend(public_models)
                 logger.info(f"Fetched {len(public_models)} models from {provider_instance.slug}.")
            else:
                logger.info(f"No models returned from {provider_instance.slug}.")
        except Exception as e:
            logger.error(f"Failed to fetch models from {provider_instance.slug}: {e}", exc_info=True)
    return all_new_models

def main():
    """Main function to update the model registry."""
    logger.info("Starting model registry update process...")

    # Instantiate providers here, after dotenv has loaded
    providers = [OpenAIProvider()] 
    # Add other providers here when they are ready, e.g., AnthropicProvider()

    existing_models_list = load_existing_models(MODELS_JSON_PATH)
    original_models_json_str = ""
    if MODELS_JSON_PATH.exists() and MODELS_JSON_PATH.is_file():
        try:
            original_models_json_str = MODELS_JSON_PATH.read_text()
        except Exception as e:
            logger.error(f"Could not read existing {MODELS_JSON_PATH} for comparison: {e}")
    
    logger.info(f"Loaded {len(existing_models_list)} existing models from {MODELS_JSON_PATH if MODELS_JSON_PATH.exists() else 'no existing file'}.")

    fetched_models_list = fetch_all_models(providers)
    logger.info(f"Fetched a total of {len(fetched_models_list)} models from all providers.")

    combined_models_map: Dict[Tuple[str, str, str], ModelEntry] = {}
    for model in existing_models_list:
        combined_models_map[(model.developer, model.model_id, model.provider)] = model

    added_count = 0
    newly_added_models: List[ModelEntry] = [] # To store the actual new models
    for model in fetched_models_list:
        if (model.developer, model.model_id, model.provider) not in combined_models_map:
            combined_models_map[(model.developer, model.model_id, model.provider)] = model
            logger.debug(f"Adding new model: {model.provider} - {model.model_id}")
            newly_added_models.append(model) # Collect new model
            added_count += 1
        else: # Model already exists, user wants to keep existing, so no update logic here for now.
            logger.debug(f"Developer {model.developer} - Model {model.model_id} already exists in {model.provider}. Not overwriting with fetched version.")

    if added_count > 0:
        logger.info(f"Added {added_count} new models to the registry.")
        # Generate Atom feed if there are new models
        logger.info(f"Generating Atom feed for {added_count} new models.")
        try:
            build_atom_feed(new_models=newly_added_models, repo_url=REPO_URL, output_path=WORKSPACE_ROOT)
            logger.info(f"Atom feed generated for {added_count} new models successfully in {WORKSPACE_ROOT}.")
        except Exception as e:
            logger.error(f"Failed to generate Atom feed: {e}", exc_info=True)
    else:
        logger.info("No new models were added from providers.")

    final_model_list = list(combined_models_map.values())
    final_model_list.sort(key=lambda m: (m.developer.lower(), m.model_id.lower(), m.provider.lower())) # Case-insensitive sort
    logger.info(f"Total models after combining and sorting: {len(final_model_list)}.")

    try:
        # Ensure consistent serialization for comparison by sorting keys in dicts
        # Pydantic's model_dump should be consistent, but explicit sort_keys for json.dumps is safer for string comparison.
        # However, model_dump(mode='json') already produces JSON-compatible types (e.g. date -> str).
        new_models_as_dicts = [model.model_dump(mode='json') for model in final_model_list]
        new_models_json_str = json.dumps(new_models_as_dicts, indent=2)

    except Exception as e:
        logger.error(f"Error serializing final model list to JSON: {e}")
        sys.exit(1)

    # Compare content
    # Normalize line endings for comparison, as git might change them depending on core.autocrlf
    normalized_original_str = original_models_json_str.replace('\r\n', '\n')
    normalized_new_str = new_models_json_str.replace('\r\n', '\n')

    if normalized_original_str == normalized_new_str and MODELS_JSON_PATH.exists():
        message = f"No content changes to {MODELS_JSON_PATH}. ({len(final_model_list)} models)"
        print(message)
        logger.info(message)
        sys.exit(0)
    else:
        logger.info(f"Changes detected or {MODELS_JSON_PATH} is new/empty. Writing new content.")
        save_models(MODELS_JSON_PATH, final_model_list)
        print(f"{MODELS_JSON_PATH} updated with {len(final_model_list)} models.")
        sys.exit(0)

if __name__ == "__main__":
    main() 