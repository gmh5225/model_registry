import os
import pytest
import responses
import requests
from datetime import date
from unittest.mock import patch

from model_registry.providers.openai import OpenAIProvider
from model_registry.schemas import ModelEntry
from dotenv import load_dotenv

load_dotenv()

# Sample API response data
SAMPLE_MODELS_DATA = {
    "object": "list",
    "data": [
        {
            "id": "gpt-4-0314",
            "object": "model",
            "created": 1687882479, # June 27, 2023
            "owned_by": "openai"
        },
        {
            "id": "gpt-3.5-turbo-0125",
            "object": "model",
            "created": 1706054400, # Jan 24, 2024
            "owned_by": "openai"
        },
        {
            "id": "dall-e-2",
            "object": "model",
            "created": 1698742602, # Oct 31, 2023
            "owned_by": "openai"
        },
        {
            "id": "ft:model:foo-bar", # Fine-tuned model
            "object": "model",
            "created": 1678886400,
            "owned_by": "user"
        },
        {
            "id": "some-ft-model:foo-bar", # Fine-tuned model
            "object": "model",
            "created": 1678886400,
            "owned_by": "user"
        },
        {
            "id": "another-model-org-owned",
            "object": "model",
            "created": 1678886400,
            "owned_by": "org-abc" # Not owned by openai
        },
        {
            "id": "model-with-date-2023-03-15", # Model with YYYY-MM-DD in id
            "object": "model",
            "created": 1678838400, # March 15, 2023
            "owned_by": "openai"
        },
         {
            "id": "model-no-date-info", # Model without any date indication in id and no 'created'
            "object": "model",
            "owned_by": "openai"
        },
        {
            "id": "model-with-invalid-date-suffix-0000", # Invalid date like MMDD where DD is 00
            "object": "model",
            "created": 1678838400,
            "owned_by": "openai"
        },
        {
            "id": "gpt-4-32k-0314", # another valid model
            "object": "model",
            "created": 1678824790, # March 14, 2023 (example)
            "owned_by": "openai"
        }
    ]
}

@pytest.fixture
def provider():
    return OpenAIProvider()

@responses.activate
def test_fetch_models_success(provider):
    # Use the API key from the environment variable
    api_key = os.getenv("OPENAI_API_KEY")
    responses.add(
        responses.GET,
        "https://api.openai.com/v1/models",
        json=SAMPLE_MODELS_DATA,
        headers={"Authorization": f"Bearer {api_key}"},
        status=200
    )
    models = list(provider.fetch_models())
    assert len(models) == len(SAMPLE_MODELS_DATA["data"])
    assert models[0]["id"] == "gpt-4-0314"
    assert responses.calls[0].request.headers["Authorization"] == f"Bearer {api_key}"

@responses.activate
def test_fetch_models_api_error(provider):
    # Use the API key from the environment variable
    api_key = os.getenv("OPENAI_API_KEY")
    responses.add(
        responses.GET,
        "https://api.openai.com/v1/models",
        json={"error": "API error"},
        status=500,
        headers={"Authorization": f"Bearer {api_key}"}
    )
    with pytest.raises(requests.exceptions.HTTPError):
        provider.fetch_models()

def test_filter_public(provider):
    filtered = list(provider.filter_public(SAMPLE_MODELS_DATA["data"]))
    assert len(filtered) == 8 # Expect 8 now: 10 total - 2 ft models
    assert not any(":ft:" in model["id"] for model in filtered)
    assert not any("ft-" in model["id"] for model in filtered)
    assert "ft:model:foo-bar" not in [m["id"] for m in filtered]
    assert "some-ft-model:foo-bar" not in [m["id"] for m in filtered]

def test_get_model_id(provider):
    assert provider.get_model_id({"id": "test-model"}) == "test-model"

def test_get_developer(provider):
    assert provider.get_developer({}) == "openai"

@pytest.mark.parametrize("model_data, expected_date_str", [
    ({"id": "model-with-date-2023-03-15", "created": 1678838400}, "2023-03-15"), # YYYY-MM-DD in ID
    ({"id": "gpt-3.5-turbo-0125", "created": 1706054400}, "2024-01-25"), # -MMDD suffix, year from created
    ({"id": "gpt-4-0613", "created": 1686585600}, "2023-06-13"), # -MMDD suffix, year from created
    ({"id": "text-davinci-003", "created": 1669852800}, "2022-12-01"), # Fallback to created timestamp (1669852800 -> 2022-12-01)
    ({"id": "model-no-date-info", "owned_by": "openai"}, "9999-12-31"), # No date info in ID, no created timestamp
    ({"id": "model-with-invalid-id-date-format", "created": 1609459200}, "2021-01-01"), # Invalid date in ID, use created
    ({"id": "model-with-future-date-in-id-2077-01-01", "created": 1609459200}, "2077-01-01"), # Future date in ID
    ({"id": "model-suffix-240101", "created": 1609459200}, "2024-01-01"), # YYYYMMDD suffix
    ({"id": "model-suffix-short-0101", "created": 1704067200}, "2024-01-01"), # MMDD suffix, year 2024 from created
    ({"id": "model-with-unparseable-created", "created": "not-a-timestamp"}, "9999-12-31"),
    ({"id": "model-with-no-created-field"}, "9999-12-31"),
    ({"id": "model-invalid-date-suffix-0000", "created": 1678838400}, "2023-03-15"), # Uses created date as "0000" is not valid MMDD
])
def test_get_release_date(provider, model_data, expected_date_str):
    expected = date.fromisoformat(expected_date_str)
    assert provider.get_release_date(model_data) == expected


def test_normalize(provider):
    model_record = {
        "id": "gpt-4-test",
        "created": 1678886400, # March 15, 2023
        "owned_by": "openai"
    }
    entry = provider.normalize(model_record)
    assert isinstance(entry, ModelEntry)
    assert entry.provider == "openai"
    assert entry.model_id == "gpt-4-test"
    assert entry.developer == "openai"
    assert entry.release_date == date(2023, 3, 15) # From created timestamp
    assert entry.status == "active"

@responses.activate
def test_public_models(provider):
    os.environ["OPENAI_API_KEY"] = "test_key_public"
    responses.add(
        responses.GET,
        "https://api.openai.com/v1/models",
        json=SAMPLE_MODELS_DATA,
        status=200
    )

    with patch.object(provider, 'filter_public', wraps=provider.filter_public) as mock_filter_public, \
         patch.object(provider, 'normalize', wraps=provider.normalize) as mock_normalize:

        models = provider.public_models()

        expected_public_ids = [
            "gpt-4-0314", "gpt-3.5-turbo-0125", "dall-e-2",
            "model-with-date-2023-03-15", "model-no-date-info", 
            "model-with-invalid-date-suffix-0000", "gpt-4-32k-0314",
            "another-model-org-owned"
        ]
        
        assert len(models) == 8 # Expect 8 (10 total - 2 ft models)

        model_ids = [m.model_id for m in models]
        for expected_id in expected_public_ids:
            assert expected_id in model_ids

        assert mock_filter_public.called
        assert mock_normalize.call_count == 8 # Expect 8

        gpt4_model = next(m for m in models if m.model_id == "gpt-4-0314")
        assert gpt4_model.release_date == date(2023, 3, 14)
        assert gpt4_model.developer == "openai"
        assert gpt4_model.provider == "openai"

        model_no_date = next(m for m in models if m.model_id == "model-no-date-info")
        assert model_no_date.release_date == date(9999, 12, 31)

        model_w_date_in_id = next(m for m in models if m.model_id == "model-with-date-2023-03-15")
        assert model_w_date_in_id.release_date == date(2023, 3, 15)

    del os.environ["OPENAI_API_KEY"] 