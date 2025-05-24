import os
import re
import datetime
import logging
from datetime import date
from typing import Any, Dict, Iterable, List

import requests

from model_registry.providers.base import Provider, retry
from model_registry.schemas import ModelEntry
from model_registry.logger import setup_logging


setup_logging()
logger = logging.getLogger("model_registry")

class OpenRouterProvider(Provider):
    slug: str = "openrouter"
    
    def __init__(self):
        """
        Initializes the OpenRouterProvider, ensuring the API key is available.
        Raises ValueError if the API key is not found.
        """
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.error("OPENROUTER_API_KEY environment variable not set. OpenRouterProvider cannot be initialized.")
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
        logger.info("OpenRouterProvider initialized successfully.")

    @retry()
    def fetch_models(self) -> Iterable[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/model-registry",  # Required by OpenRouter
            "X-Title": "Model Registry"  # Optional but recommended
        }
        response = requests.get("https://openrouter.ai/api/v1/models", headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json().get("data", [])

    def filter_public(self, raw: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        # OpenRouter likely returns only public models, but we can add filtering logic if needed
        # For now, return all models
        return raw

    def get_model_id(self, model_record: Dict[str, Any]) -> str:
        # Return the full ID as-is (e.g., "anthropic/claude-sonnet-4")
        return model_record["id"]

    def get_developer(self, model_record: Dict[str, Any]) -> str:
        """
        Extract the developer from the model ID.
        For example: "anthropic/claude-sonnet-4" -> "anthropic"
        """
        model_id = model_record.get("id", "")
        
        # Split by '/' and take the first part as the developer
        parts = model_id.split('/')
        if len(parts) >= 2:
            return parts[0]
        
        # If no slash found, try to infer from the name or return "unknown"
        name = model_record.get("name", "")
        
        # Common patterns in names
        if name.lower().startswith("anthropic:"):
            return "anthropic"
        elif name.lower().startswith("openai:"):
            return "openai"
        elif name.lower().startswith("google:"):
            return "google"
        elif name.lower().startswith("meta:"):
            return "meta"
        elif name.lower().startswith("mistral:"):
            return "mistral"
        elif name.lower().startswith("cohere:"):
            return "cohere"
        
        # If we can't determine the developer, return "unknown"
        logger.warning(f"Could not determine developer for model: {model_id}")
        return "unknown"

    def get_release_date(self, model_record: Dict[str, Any]) -> date:
        """
        Extract the release date from the 'created' timestamp.
        The 'created' field appears to be a Unix timestamp.
        """
        created_timestamp = model_record.get("created")
        if created_timestamp is not None:
            try:
                # Convert Unix timestamp to date object (not datetime)
                return datetime.datetime.fromtimestamp(created_timestamp, tz=datetime.timezone.utc).date()
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to parse created timestamp {created_timestamp}: {e}")
        
        # Fallback to a far future date if no date information can be parsed
        return date(9999, 12, 31)

    def normalize(self, model_record: Dict[str, Any]) -> ModelEntry:
        """
        Transform OpenRouter model record to ModelEntry.
        """
        # Check if model has any specific status indication
        # For now, assume all models from OpenRouter are active
        status = "active"
        
        # Check if the model is marked as deprecated in the description or name
        description = model_record.get("description", "").lower()
        name = model_record.get("name", "").lower()
        if "deprecated" in description or "deprecated" in name:
            status = "deprecated"
        
        return ModelEntry(
            provider=self.slug,
            developer=self.get_developer(model_record),
            model_id=self.get_model_id(model_record),
            release_date=self.get_release_date(model_record),
            status=status,
        )

    def public_models(self) -> List[ModelEntry]:
        """
        Override to handle errors more gracefully and provide better logging.
        """
        try:
            raw_models = self.fetch_models()
            public_raw_models = self.filter_public(raw_models)
            
            models = []
            for model in public_raw_models:
                try:
                    models.append(self.normalize(model))
                except Exception as e:
                    logger.error(f"Failed to normalize model {model.get('id', 'unknown')}: {e}")
                    continue
                    
            logger.info(f"Successfully fetched {len(models)} models from OpenRouter")
            return models
        except Exception as e:
            logger.error(f"Failed to fetch models from OpenRouter: {e}")
            return []


if __name__ == "__main__":
    # Test the provider
    provider = OpenRouterProvider()
    models = provider.fetch_models()
    print(f"Fetched {len(models)} models")
    if models:
        print("First model:", models[0])
    
    print("\n================")
    public_models = provider.public_models()
    print(f"Fetched {len(public_models)} public models")
    if public_models:
        first_model = public_models[0]
        print("First public model:")
        print(f"  Provider: {first_model.provider}")
        print(f"  Developer: {first_model.developer}")
        print(f"  Model ID: {first_model.model_id}")
        print(f"  Release Date: {first_model.release_date.isoformat()}")  # Show as ISO string
        print(f"  Status: {first_model.status}")
        print(f"  Date Type: {type(first_model.release_date).__name__}")  # Confirm it's a date object
    print("================") 