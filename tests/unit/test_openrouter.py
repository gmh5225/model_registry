import os
import pytest
import responses
import requests
from datetime import date
from unittest.mock import patch

from model_registry.providers.openrouter import OpenRouterProvider
from model_registry.schemas import ModelEntry
from dotenv import load_dotenv

load_dotenv()

# Sample API response data based on OpenRouter's API format
SAMPLE_MODELS_DATA = {
    "data": [
        {
            "id": "anthropic/claude-sonnet-4",
            "hugging_face_id": "",
            "name": "Anthropic: Claude Sonnet 4",
            "created": 1737504000,  # 2025-01-22
            "description": "Claude Sonnet 4 significantly enhances the capabilities...",
            "context_length": 200000,
            "architecture": {
                "modality": "text+image->text",
                "input_modalities": ["image", "text"],
                "output_modalities": ["text"],
                "tokenizer": "Claude"
            },
            "pricing": {
                "prompt": "0.000003",
                "completion": "0.000015",
                "image": "0.001",
                "request": "0"
            }
        },
        {
            "id": "openai/gpt-4o",
            "hugging_face_id": "",
            "name": "OpenAI: GPT-4o",
            "created": 1715212800,  # 2024-05-09
            "description": "GPT-4o is OpenAI's new flagship multimodal model...",
            "context_length": 128000,
            "architecture": {
                "modality": "text+image->text",
                "input_modalities": ["image", "text"],
                "output_modalities": ["text"],
                "tokenizer": "GPT"
            },
            "pricing": {
                "prompt": "0.000005",
                "completion": "0.000015",
                "image": "0.001",
                "request": "0"
            }
        },
        {
            "id": "google/gemini-pro-1.5",
            "hugging_face_id": "",
            "name": "Google: Gemini Pro 1.5",
            "created": 1709164800,  # 2024-02-29
            "description": "Google's advanced Gemini model...",
            "context_length": 1000000,
            "architecture": {
                "modality": "text+image->text",
                "input_modalities": ["image", "text"],
                "output_modalities": ["text"],
                "tokenizer": "Gemini"
            },
            "pricing": {
                "prompt": "0.000003",
                "completion": "0.000015",
                "image": "0.001",
                "request": "0"
            }
        },
        {
            "id": "meta-llama/llama-3.1-8b-instruct",
            "hugging_face_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "name": "Meta: Llama 3.1 8B Instruct",
            "created": 1720137600,  # 2024-07-05
            "description": "Meta's Llama 3.1 8B instruction-tuned model...",
            "context_length": 128000,
            "architecture": {
                "modality": "text->text",
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "tokenizer": "Llama"
            },
            "pricing": {
                "prompt": "0.0000002",
                "completion": "0.0000002",
                "request": "0"
            }
        },
        {
            "id": "mistralai/mistral-7b-instruct",
            "hugging_face_id": "mistralai/Mistral-7B-Instruct-v0.1",
            "name": "Mistral: 7B Instruct",
            "created": 1698019200,  # 2023-10-23
            "description": "Mistral's 7B instruction-tuned model...",
            "context_length": 32768,
            "architecture": {
                "modality": "text->text",
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "tokenizer": "Mistral"
            },
            "pricing": {
                "prompt": "0.0000002",
                "completion": "0.0000002",
                "request": "0"
            }
        },
        {
            "id": "deprecated-model/old-version",
            "hugging_face_id": "",
            "name": "Deprecated Model: Old Version",
            "created": 1640995200,  # 2022-01-01
            "description": "This model is deprecated and should not be used...",
            "context_length": 4096,
            "architecture": {
                "modality": "text->text",
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "tokenizer": "GPT"
            },
            "pricing": {
                "prompt": "0.000001",
                "completion": "0.000001",
                "request": "0"
            }
        },
        {
            "id": "unknown-provider/some-model",
            "hugging_face_id": "",
            "name": "Some Model Name",
            "created": 1704067200,  # 2024-01-01
            "description": "A model from an unknown provider...",
            "context_length": 8192,
            "architecture": {
                "modality": "text->text",
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "tokenizer": "Other"
            },
            "pricing": {
                "prompt": "0.000001",
                "completion": "0.000001",
                "request": "0"
            }
        },
        {
            "id": "no-slash-model",
            "hugging_face_id": "",
            "name": "OpenAI: GPT Model",
            "created": 1704067200,  # 2024-01-01
            "description": "A model without slash in ID...",
            "context_length": 8192,
            "architecture": {
                "modality": "text->text",
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "tokenizer": "GPT"
            },
            "pricing": {
                "prompt": "0.000001",
                "completion": "0.000001",
                "request": "0"
            }
        },
        {
            "id": "model-no-created-field",
            "hugging_face_id": "",
            "name": "Some Model",
            "description": "A model without created timestamp...",
            "context_length": 8192,
            "architecture": {
                "modality": "text->text",
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "tokenizer": "Other"
            },
            "pricing": {
                "prompt": "0.000001",
                "completion": "0.000001",
                "request": "0"
            }
        }
    ]
}

@pytest.fixture
def provider():
    return OpenRouterProvider()

@responses.activate
def test_fetch_models_success(provider):
    # Use the API key from the environment variable
    api_key = os.getenv("OPENROUTER_API_KEY")
    responses.add(
        responses.GET,
        "https://openrouter.ai/api/v1/models",
        json=SAMPLE_MODELS_DATA,
        status=200
    )
    models = list(provider.fetch_models())
    assert len(models) == len(SAMPLE_MODELS_DATA["data"])
    assert models[0]["id"] == "anthropic/claude-sonnet-4"
    
    # Check that the request has the correct headers
    assert len(responses.calls) == 1
    request_headers = responses.calls[0].request.headers
    assert request_headers["Authorization"] == f"Bearer {api_key}"
    assert request_headers["HTTP-Referer"] == "https://github.com/model-registry"
    assert request_headers["X-Title"] == "Model Registry"

@responses.activate
def test_fetch_models_api_error(provider):
    responses.add(
        responses.GET,
        "https://openrouter.ai/api/v1/models",
        json={"error": "API error"},
        status=500
    )
    with pytest.raises(requests.exceptions.HTTPError):
        provider.fetch_models()

def test_filter_public(provider):
    # OpenRouter likely returns only public models, so filter should return all
    filtered = list(provider.filter_public(SAMPLE_MODELS_DATA["data"]))
    assert len(filtered) == len(SAMPLE_MODELS_DATA["data"])
    assert filtered == SAMPLE_MODELS_DATA["data"]

def test_get_model_id(provider):
    assert provider.get_model_id({"id": "anthropic/claude-sonnet-4"}) == "anthropic/claude-sonnet-4"

@pytest.mark.parametrize("model_data, expected_developer", [
    ({"id": "anthropic/claude-sonnet-4", "name": "Anthropic: Claude Sonnet 4"}, "anthropic"),
    ({"id": "openai/gpt-4o", "name": "OpenAI: GPT-4o"}, "openai"),
    ({"id": "google/gemini-pro-1.5", "name": "Google: Gemini Pro 1.5"}, "google"),
    ({"id": "meta-llama/llama-3.1-8b-instruct", "name": "Meta: Llama 3.1"}, "meta-llama"),
    ({"id": "mistralai/mistral-7b-instruct", "name": "Mistral: 7B Instruct"}, "mistralai"),
    ({"id": "no-slash-model", "name": "Anthropic: Claude Model"}, "anthropic"),  # Infer from name
    ({"id": "no-slash-model", "name": "OpenAI: GPT Model"}, "openai"),  # Infer from name
    ({"id": "no-slash-model", "name": "Google: Gemini Model"}, "google"),  # Infer from name
    ({"id": "no-slash-model", "name": "Meta: Llama Model"}, "meta"),  # Infer from name
    ({"id": "no-slash-model", "name": "Mistral: Model"}, "mistral"),  # Infer from name
    ({"id": "no-slash-model", "name": "Cohere: Model"}, "cohere"),  # Infer from name
    ({"id": "no-slash-model", "name": "Unknown Model"}, "unknown"),  # Can't determine
    ({"id": "unknown-provider/some-model", "name": "Some Model"}, "unknown-provider"),  # From ID
])
def test_get_developer(provider, model_data, expected_developer):
    assert provider.get_developer(model_data) == expected_developer

@pytest.mark.parametrize("model_data, expected_date_str", [
    ({"id": "anthropic/claude-sonnet-4", "created": 1737504000}, "2025-01-22"),  # Valid timestamp
    ({"id": "openai/gpt-4o", "created": 1715212800}, "2024-05-09"),  # Valid timestamp
    ({"id": "google/gemini-pro-1.5", "created": 1709164800}, "2024-02-29"),  # Valid timestamp
    ({"id": "model-no-created-field"}, "9999-12-31"),  # No created field
    ({"id": "model-invalid-created", "created": "not-a-timestamp"}, "9999-12-31"),  # Invalid timestamp
    ({"id": "model-zero-created", "created": 0}, "1970-01-01"),  # Zero timestamp (Unix epoch)
    ({"id": "model-null-created", "created": None}, "9999-12-31"),  # Null timestamp
])
def test_get_release_date(provider, model_data, expected_date_str):
    expected = date.fromisoformat(expected_date_str)
    assert provider.get_release_date(model_data) == expected

@pytest.mark.parametrize("model_data, expected_status", [
    ({"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "description": "Latest model", "created": 1737504000}, "active"),
    ({"id": "deprecated-model/old", "name": "Deprecated Model", "description": "This is deprecated", "created": 1640995200}, "deprecated"),
    ({"id": "old-model/legacy", "name": "Legacy deprecated model", "description": "Old model", "created": 1640995200}, "deprecated"),
    ({"id": "normal-model/v1", "name": "Normal Model", "description": "A normal model", "created": 1704067200}, "active"),
])
def test_normalize_status_detection(provider, model_data, expected_status):
    entry = provider.normalize(model_data)
    assert entry.status == expected_status

def test_normalize(provider):
    model_record = {
        "id": "anthropic/claude-sonnet-4",
        "name": "Anthropic: Claude Sonnet 4",
        "created": 1737504000,  # 2025-01-22
        "description": "Claude Sonnet 4 model..."
    }
    entry = provider.normalize(model_record)
    assert isinstance(entry, ModelEntry)
    assert entry.provider == "openrouter"
    assert entry.model_id == "anthropic/claude-sonnet-4"
    assert entry.developer == "anthropic"
    assert entry.release_date == date(2025, 1, 22)
    assert entry.status == "active"

@responses.activate
def test_public_models(provider):
    api_key = os.getenv("OPENROUTER_API_KEY", "test_key_public")
    responses.add(
        responses.GET,
        "https://openrouter.ai/api/v1/models",
        json=SAMPLE_MODELS_DATA,
        status=200
    )

    with patch.object(provider, 'filter_public', wraps=provider.filter_public) as mock_filter_public, \
         patch.object(provider, 'normalize', wraps=provider.normalize) as mock_normalize:

        models = provider.public_models()

        expected_model_ids = [
            "anthropic/claude-sonnet-4", "openai/gpt-4o", "google/gemini-pro-1.5",
            "meta-llama/llama-3.1-8b-instruct", "mistralai/mistral-7b-instruct",
            "deprecated-model/old-version", "unknown-provider/some-model",
            "no-slash-model", "model-no-created-field"
        ]
        
        assert len(models) == 9  # All models should be included
        
        model_ids = [m.model_id for m in models]
        for expected_id in expected_model_ids:
            assert expected_id in model_ids

        assert mock_filter_public.called
        assert mock_normalize.call_count == 9

        # Test specific model properties
        claude_model = next(m for m in models if m.model_id == "anthropic/claude-sonnet-4")
        assert claude_model.release_date == date(2025, 1, 22)
        assert claude_model.developer == "anthropic"
        assert claude_model.provider == "openrouter"
        assert claude_model.status == "active"

        # Test model without created field
        model_no_date = next(m for m in models if m.model_id == "model-no-created-field")
        assert model_no_date.release_date == date(9999, 12, 31)

        # Test deprecated model detection
        deprecated_model = next(m for m in models if m.model_id == "deprecated-model/old-version")
        assert deprecated_model.status == "deprecated"

        # Test developer extraction from name when no slash in ID
        no_slash_model = next(m for m in models if m.model_id == "no-slash-model")
        assert no_slash_model.developer == "openai"  # Should be inferred from "OpenAI: GPT Model"

@responses.activate
def test_public_models_api_failure(provider):
    responses.add(
        responses.GET,
        "https://openrouter.ai/api/v1/models",
        json={"error": "API error"},
        status=500
    )
    
    # Should return empty list on API failure
    models = provider.public_models()
    assert models == []

def test_public_models_normalization_failure(provider):
    # Test case where individual model normalization fails
    with patch.object(provider, 'fetch_models') as mock_fetch, \
         patch.object(provider, 'filter_public') as mock_filter, \
         patch.object(provider, 'normalize') as mock_normalize:
        
        mock_fetch.return_value = [{"id": "test-model", "created": 1234567890}]
        mock_filter.return_value = [{"id": "test-model", "created": 1234567890}]
        mock_normalize.side_effect = ValueError("Normalization failed")
        
        models = provider.public_models()
        assert models == []  # Should return empty list if normalization fails 