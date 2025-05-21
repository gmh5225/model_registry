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

class OpenAIProvider(Provider):
    slug: str = "openai"
    # api_key: str # Removed from here if not strictly needed, __init__ will handle it.
    
    def __init__(self):
        """
        Initializes the OpenAIProvider, ensuring the API key is available.
        Raises ValueError if the API key is not found.
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.error("OPENAI_API_KEY environment variable not set. OpenAIProvider cannot be initialized.")
            raise ValueError("OPENAI_API_KEY environment variable not set")
        logger.info("OpenAIProvider initialized successfully.")

    @retry()
    def fetch_models(self) -> Iterable[Dict[str, Any]]:

        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get("https://api.openai.com/v1/models", headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json().get("data", [])

    def filter_public(self, raw: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        return [
            m for m in raw
            if "ft:" not in m.get("id", "")
               and "ft-" not in m.get("id", "")
        ]

    def get_model_id(self, model_record: Dict[str, Any]) -> str:
        return model_record["id"]

    def get_developer(self, model_record: Dict[str, Any]) -> str:
        return "openai"

    def get_release_date(self, model_record: Dict[str, Any]) -> date:
        model_id = model_record.get("id", "")

        # Pattern 1: YYYY-MM-DD in ID (e.g., model-2023-03-15)
        match_iso = re.search(r"(\d{4}-\d{2}-\d{2})", model_id)
        if match_iso:
            try:
                return date.fromisoformat(match_iso.group(1))
            except ValueError:
                pass

        # Pattern 2: -YYYYMMDD suffix (e.g., model-20240101)
        match_yyyymmdd = re.search(r"-(\d{4})(\d{2})(\d{2})$", model_id)
        if match_yyyymmdd:
            try:
                y, m, d = map(int, match_yyyymmdd.groups())
                return date(y, m, d)
            except ValueError:
                pass
        
        # Pattern 3: -YYMMDD suffix (e.g., model-240101 for 2024-01-01)
        match_yymmdd = re.search(r"-(\d{2})(\d{2})(\d{2})$", model_id)
        if match_yymmdd:
            try:
                ys, ms, ds = match_yymmdd.groups()
                year = int(f"20{ys}") # Assuming 20xx century
                month = int(ms)
                day = int(ds)
                return date(year, month, day)
            except ValueError:
                pass
        
        # Pattern 4: -MMDD suffix (e.g., gpt-3.5-turbo-0125). Use year from 'created' timestamp.
        match_mmdd = re.search(r"-(\d{2})(\d{2})$", model_id)
        if match_mmdd:
            created_timestamp = model_record.get("created")
            if created_timestamp is not None:
                try:
                    year_of_creation = datetime.datetime.fromtimestamp(created_timestamp, tz=datetime.timezone.utc).year
                    m, d = map(int, match_mmdd.groups())
                    return date(year_of_creation, m, d)
                except (ValueError, TypeError):
                    pass 

        # Fallback to 'created' timestamp if present
        created_timestamp = model_record.get("created")
        if created_timestamp is not None:
            try:
                return datetime.datetime.fromtimestamp(created_timestamp, tz=datetime.timezone.utc).date()
            except (TypeError, ValueError):
                pass

        # Fallback to a far future date if no other date information can be parsed
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