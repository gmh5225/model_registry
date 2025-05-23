import os
import re
import logging
import datetime
from datetime import date
from typing import Any, Dict, Iterable, List

from dotenv import load_dotenv

load_dotenv()

import requests

from model_registry.providers.base import Provider, retry
from model_registry.schemas import ModelEntry
from model_registry.logger import setup_logging

setup_logging()
logger = logging.getLogger("model_registry")

class GeminiProvider(Provider):
    slug: str = "gemini"

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.error(
                "GEMINI_API_KEY environment variable not set. GeminiProvider cannot be initialized."
            )
            raise ValueError("GEMINI_API_KEY environment variable not set")
        logger.info("GeminiProvider initialized successfully.")

    @retry()
    def fetch_models(self) -> Iterable[Dict[str, Any]]:
        """
        Calls Google's Gemini models.list endpoint with pagination support.
        Ref: https://ai.google.dev/api/models#method:-models.list
        """
        all_models = []
        page_token = None
        page_size = 100  # Use a reasonable page size
        
        while True:
            try:
                # Build URL with pagination parameters
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
                params = {"pageSize": page_size}
                if page_token:
                    params["pageToken"] = page_token
                
                response = requests.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                models = data.get("models", [])
                all_models.extend(models)
                
                # Check if there's a next page
                page_token = data.get("nextPageToken")
                if not page_token:
                    # No more pages, exit the loop
                    break
                    
                logger.debug(f"Fetched {len(models)} models, continuing to next page...")
                
            except requests.exceptions.RequestException as e:
                # If this is the first page (no models fetched yet), re-raise the exception
                # so the retry decorator can handle it
                if not all_models:
                    raise
                
                logger.warning(f"Error fetching models page: {e}")
                # Return what we have so far rather than failing completely
                break
            except Exception as e:
                # If this is the first page (no models fetched yet), re-raise the exception
                if not all_models:
                    raise
                
                logger.error(f"Unexpected error during pagination: {e}")
                # Return what we have so far
                break
        
        logger.info(f"Successfully fetched {len(all_models)} total models from Gemini API")
        return all_models

    def filter_public(self, raw: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        # Endpoint already returns only generally-available models
        return raw

    def get_model_id(self, model_record: Dict[str, Any]) -> str:
        # e.g. "models/gemini-1.5-flash-001"
        return model_record.get("name", "")

    def get_developer(self, model_record: Dict[str, Any]) -> str:
        return "google"

    def get_release_date(self, model_record: Dict[str, Any]) -> date:
        # Google does not expose release dates yet.  Try to parse -YYYYMMDD in the name
        name = model_record.get("name", "")
        match = re.search(r"-(\d{4})(\d{2})(\d{2})$", name)
        if match:
            try:
                y, m, d = map(int, match.groups())
                return date(y, m, d)
            except ValueError:
                pass
        return date(9999, 12, 31)  # Unknown / future placeholder

    def normalize(self, model_record: Dict[str, Any]) -> ModelEntry:
        return ModelEntry(
            provider=self.slug,
            developer=self.get_developer(model_record),
            model_id=self.get_model_id(model_record),
            release_date=self.get_release_date(model_record),
            status="active",
        )

    def public_models(self) -> List[ModelEntry]:
        raw_models = self.fetch_models()
        public_raw_models = self.filter_public(raw_models)
        return [self.normalize(m) for m in public_raw_models]

if __name__ == "__main__":
    provider = GeminiProvider()
    models = provider.fetch_models()
    print(f"Fetched {len(models)} models")
    print(models)

    print ("================")
    public_models = provider.public_models()
    print (f"Fetched {len(public_models)} public models")
    print (public_models)
    print ("================")