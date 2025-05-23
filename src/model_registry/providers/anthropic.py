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

class AnthropicProvider(Provider):
    slug: str = "anthropic"
    # api_key: str # Removed from here if not strictly needed, __init__ will handle it.
    
    def __init__(self):
        """
        Initializes the AnthropicProvider, ensuring the API key is available.
        Raises ValueError if the API key is not found.
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.error("ANTHROPIC_API_KEY environment variable not set. AnthropicProvider cannot be initialized.")
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        logger.info("AnthropicProvider initialized successfully.")

    @retry()
    def fetch_models(self) -> Iterable[Dict[str, Any]]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        response = requests.get("https://api.anthropic.com/v1/models", headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json().get("data", [])

    def filter_public(self, raw: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        return raw

    def get_model_id(self, model_record: Dict[str, Any]) -> str:
        return model_record["id"]

    def get_developer(self, model_record: Dict[str, Any]) -> str:
        return "anthropic"

    def get_release_date(self, model_record: Dict[str, Any]) -> date:
        # Use the created_at timestamp from Anthropic API
        created_at = model_record.get("created_at")
        if created_at:
            try:
                # Parse the ISO format timestamp (e.g., "2025-02-19T00:00:00Z")
                return datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
            except (ValueError, TypeError):
                pass
        
        # Fallback to a far future date if no date information can be parsed
        return date(9999, 12, 31)

    def normalize(self, model_record: Dict[str, Any]) -> ModelEntry:
        return ModelEntry(
            provider=self.slug,
            developer=self.get_developer(model_record),
            model_id=self.get_model_id(model_record),
            release_date=self.get_release_date(model_record),
            status="active",  # Assuming active, OpenAI API doesn't specify status directly for public models
        )

    def public_models(self) -> List[ModelEntry]:
        raw_models = self.fetch_models()
        public_raw_models = self.filter_public(raw_models)
        return [self.normalize(model) for model in public_raw_models]
    
if __name__ == "__main__":
    provider = AnthropicProvider()
    models = provider.fetch_models()
    print(f"Fetched {len(models)} models")
    print(models)

    print ("================")
    public_models = provider.public_models()
    print (f"Fetched {len(public_models)} public models")
    print (public_models)
    print ("================")