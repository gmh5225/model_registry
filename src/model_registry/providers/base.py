from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date
import logging
import time
from functools import wraps
from typing import Any, Dict, List

from model_registry.schemas import ModelEntry

# Initialize logger
logger = logging.getLogger(__name__)


def retry(attempts: int = 3, delay: int = 1, backoff: int = 2):
    """
    Retry decorator with exponential backoff.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _attempts = attempts
            _current_delay = delay
            last_exception = None
            for attempt in range(_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == _attempts - 1:
                        break
                    logger.warning(
                        f"Function {func.__name__} failed with {e}. "
                        f"Retrying in {_current_delay}s... ({attempt + 1}/{_attempts} attempts)"
                    )
                    time.sleep(_current_delay)
                    _current_delay *= backoff
            
            logger.error(
                f"Function {func.__name__} failed after {attempts} attempts. Last error: {last_exception}"
            )
            raise last_exception # type: ignore
        return wrapper
    return decorator


class Provider(ABC):
    """
    Abstract base class for model providers.
    Concrete providers must define the `slug` class attribute.
    """
    slug: str 
    api_key: str

    @abstractmethod
    def fetch_models(self) -> Iterable[Dict[str, Any]]:
        """
        Fetches raw model data from the provider.
        This method is expected to make network calls and should be decorated with `retry`.
        """
        pass

    @abstractmethod
    def filter_public(self, raw_data: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        """
        Filters the raw model data to include only publicly accessible models
        and performs any initial common transformations.
        """
        pass

    @abstractmethod
    def get_model_id(self, model_record: Dict[str, Any]) -> str:
        """
        Extracts the unique model ID from a given model record.
        """
        pass
    
    @abstractmethod
    def get_developer(self, model_record: Dict[str, Any]) -> str:
        """
        Determines the developer of the model from a given model record.
        """
        pass

    @abstractmethod
    def get_release_date(self, model_record: Dict[str, Any]) -> date:
        """
        Extracts or determines the release date of the model from a given model record.
        Concrete implementations should handle cases where a date is not available,
        possibly returning a sensible default like date(9999, 12, 31) or date.today().
        """
        pass

    def normalize(self, model_record: Dict[str, Any]) -> ModelEntry:
        """
        Transforms a raw model record (after filtering) into a ModelEntry object.
        """
        status_val = model_record.get("status")

        entry_data = {
            "provider": self.slug,
            "model_id": self.get_model_id(model_record),
            "release_date": self.get_release_date(model_record),
            "developer": self.get_developer(model_record),
        }
        # Only include status if explicitly provided in model_record,
        # otherwise Pydantic's default in ModelEntry will be used.
        if status_val is not None:
            entry_data["status"] = status_val
            
        return ModelEntry(**entry_data)

    def public_models(self) -> List[ModelEntry]:
        """
        Fetches, filters, and normalizes models from the provider.
        Returns a list of ModelEntry objects.
        """
        models: List[ModelEntry] = []
        try:
            raw_data = self.fetch_models()
            public_data = self.filter_public(raw_data)
            
            for record in public_data:
                try:
                    models.append(self.normalize(record))
                except Exception as e:
                    logger.error(
                        f"Error normalizing record for provider {self.slug}: {record}. Error: {e}",
                        exc_info=True
                    )
        except Exception as e:
            logger.error(
                f"Error fetching or filtering models for provider {self.slug}: {e}",
                exc_info=True
            )
            # Return an empty list if the provider itself fails catastrophically
        return models 