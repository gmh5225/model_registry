import pytest
from datetime import date
from typing import Iterable, Dict, Any, List, Callable
from unittest.mock import MagicMock, patch, call
import logging

from model_registry.schemas import ModelEntry
from model_registry.providers.base import Provider, retry

# Configure logging for tests (e.g., to see retry warnings if needed)
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DummyProvider(Provider):
    slug = "dummy"

    def __init__(self,
                 mock_fetch_data: List[Dict[str, Any]] = None,
                 mock_filter_func: Callable[[Iterable[Dict[str, Any]]], Iterable[Dict[str, Any]]] = None,
                 fail_fetch_times: int = 0,
                 fail_normalize_records: List[str] = None, # List of model_ids to fail normalization for
                 custom_model_id_logic: Callable[[Dict[str, Any]], str] = None,
                 custom_developer_logic: Callable[[Dict[str, Any]], str] = None,
                 custom_release_date_logic: Callable[[Dict[str, Any]], date] = None
                ):
        self.mock_fetch_data = mock_fetch_data if mock_fetch_data is not None else []
        self.mock_filter_func = mock_filter_func
        self.fetch_call_count = 0
        self._fail_fetch_times_current = fail_fetch_times
        self.fail_normalize_records = fail_normalize_records if fail_normalize_records is not None else []
        self._custom_model_id_logic = custom_model_id_logic
        self._custom_developer_logic = custom_developer_logic
        self._custom_release_date_logic = custom_release_date_logic

    @retry(attempts=3, delay=0.01, backoff=1) # Use small delay for tests
    def fetch_models(self) -> Iterable[Dict[str, Any]]:
        self.fetch_call_count += 1
        if self._fail_fetch_times_current > 0:
            self._fail_fetch_times_current -= 1
            raise Exception(f"Simulated fetch error for {self.slug}")
        return self.mock_fetch_data

    def filter_public(self, raw_data: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        if self.mock_filter_func:
            return self.mock_filter_func(raw_data)
        return [r for r in raw_data if r.get("is_public", True)] # Default filter logic for tests

    def get_model_id(self, model_record: Dict[str, Any]) -> str:
        if self._custom_model_id_logic:
            return self._custom_model_id_logic(model_record)
        model_id = model_record.get("model_id", "default-id")
        if model_id in self.fail_normalize_records:
             # Simulate error during get_model_id for specific records to test normalize error handling
             raise ValueError(f"Simulated normalization error for model_id: {model_id}")
        return model_id

    def get_developer(self, model_record: Dict[str, Any]) -> str:
        if self._custom_developer_logic:
            return self._custom_developer_logic(model_record)
        return model_record.get("developer", "Default Developer")

    def get_release_date(self, model_record: Dict[str, Any]) -> date:
        if self._custom_release_date_logic:
            return self._custom_release_date_logic(model_record)
        date_str = model_record.get("release_date_str")
        if date_str:
            return date.fromisoformat(date_str)
        return date(2023, 1, 1)


@pytest.fixture
def sample_raw_data_fixture(): # Renamed to avoid conflict if used as arg and func name
    return [
        {"model_id": "model1", "developer": "DevA", "release_date_str": "2023-01-01", "status": "active", "is_public": True},
        {"model_id": "model2", "developer": "DevB", "release_date_str": "2023-02-15", "is_public": True},
        {"model_id": "model3", "developer": "DevA", "release_date_str": "2022-12-20", "is_public": False},
        {"model_id": "model4", "custom_field": "value"} # No explicit public flag, default to True in DummyProvider
    ]

@pytest.fixture
def expected_model_entries():
    return [
        ModelEntry(provider="dummy", model_id="model1", release_date=date(2023,1,1), developer="DevA", status="active"),
        ModelEntry(provider="dummy", model_id="model2", release_date=date(2023,2,15), developer="DevB", status="active"),
        # model3 is filtered out by default filter
        ModelEntry(provider="dummy", model_id="default-id", release_date=date(2023,1,1), developer="Default Developer", status="active"), # model4 processing
    ]


def test_public_models_success(sample_raw_data_fixture):
    provider = DummyProvider(mock_fetch_data=sample_raw_data_fixture)
    expected = [
        ModelEntry(provider="dummy", model_id="model1", release_date=date(2023,1,1), developer="DevA", status="active"),
        ModelEntry(provider="dummy", model_id="model2", release_date=date(2023,2,15), developer="DevB", status="active"),
        ModelEntry(provider="dummy", model_id="model4", release_date=date(2023,1,1), developer="Default Developer", status="active")
    ]

    result = provider.public_models()
    assert provider.fetch_call_count == 1
    assert len(result) == len(expected)
    assert sorted(result, key=lambda m: m.model_id) == sorted(expected, key=lambda m: m.model_id)

def test_public_models_fetch_fails_completely():
    provider = DummyProvider(fail_fetch_times=3) # Fail all 3 attempts
    result = provider.public_models()
    assert provider.fetch_call_count == 3
    assert result == []

def test_public_models_normalize_error_skips_record(sample_raw_data_fixture, caplog):
    provider = DummyProvider(mock_fetch_data=sample_raw_data_fixture, fail_normalize_records=["model2"])
    
    with caplog.at_level(logging.ERROR):
        result = provider.public_models()
    
    assert len(result) == 2
    assert "model1" in [m.model_id for m in result]
    assert "model4" in [m.model_id for m in result]
    assert "model2" not in [m.model_id for m in result]
    
    assert "Error normalizing record for provider dummy" in caplog.text
    assert "Simulated normalization error for model_id: model2" in caplog.text

def test_public_models_custom_filter(sample_raw_data_fixture):
    custom_filter = lambda raw: [r for r in raw if r.get("developer") == "DevA" and r.get("is_public", True)]
    provider = DummyProvider(mock_fetch_data=sample_raw_data_fixture, mock_filter_func=custom_filter)
    result = provider.public_models()
    assert len(result) == 1
    assert result[0].model_id == "model1"

@patch("time.sleep", return_value=None)
def test_retry_decorator_success_on_first_try(mock_sleep):
    mock_func = MagicMock(return_value="success")
    mock_func.__name__ = "mock_func_name"
    decorated_func = retry(attempts=3, delay=0.01)(mock_func)
    assert decorated_func() == "success"
    mock_func.assert_called_once()
    mock_sleep.assert_not_called()

@patch("time.sleep", return_value=None)
def test_retry_decorator_success_on_retry(mock_sleep, caplog):
    mock_func = MagicMock()
    mock_func.__name__ = "mock_func_name"
    mock_func.side_effect = [Exception("fail1"), Exception("fail2"), "success"]
    
    decorated_func = retry(attempts=3, delay=0.01, backoff=2)(mock_func)
    
    with caplog.at_level(logging.WARNING):
        assert decorated_func() == "success"
    
    assert mock_func.call_count == 3
    mock_sleep.assert_has_calls([call(0.01), call(0.01 * 2)])

    assert "Retrying in 0.01s... (1/3 attempts)" in caplog.text
    assert "Retrying in 0.02s... (2/3 attempts)" in caplog.text

@patch("time.sleep", return_value=None)
def test_retry_decorator_failure_after_all_attempts(mock_sleep, caplog):
    mock_func = MagicMock(side_effect=Exception("persistent failure"))
    mock_func.__name__ = "mock_func_name"
    decorated_func = retry(attempts=3, delay=0.01)(mock_func)
    
    with pytest.raises(Exception, match="persistent failure"):
      with caplog.at_level(logging.ERROR):
          decorated_func()
        
    assert mock_func.call_count == 3
    assert f"Function {mock_func.__name__} failed after 3 attempts. Last error: persistent failure" in caplog.text

def test_dummy_provider_fetch_retries(caplog):
    provider = DummyProvider(mock_fetch_data=[{"model_id": "test"}], fail_fetch_times=2)
    
    with caplog.at_level(logging.WARNING):
        models = provider.public_models()
    
    assert provider.fetch_call_count == 3
    assert len(models) == 1
    assert models[0].model_id == "test"
    assert "Retrying in 0.01s... (1/3 attempts)" in caplog.text
    assert "Retrying in 0.01s... (2/3 attempts)" in caplog.text