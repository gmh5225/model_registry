import os
import pytest
import responses
import requests
from datetime import date
from unittest.mock import patch

from model_registry.providers.anthropic import AnthropicProvider
from model_registry.schemas import ModelEntry
from dotenv import load_dotenv

load_dotenv()

# Sample API response data based on the actual output
SAMPLE_MODELS_DATA = {
    "data": [
        {
            "type": "model",
            "id": "claude-opus-4-20250514",
            "display_name": "Claude Opus 4",
            "created_at": "2025-05-22T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-sonnet-4-20250514",
            "display_name": "Claude Sonnet 4",
            "created_at": "2025-05-22T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-3-7-sonnet-20250219",
            "display_name": "Claude Sonnet 3.7",
            "created_at": "2025-02-24T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-3-5-sonnet-20241022",
            "display_name": "Claude Sonnet 3.5 (New)",
            "created_at": "2024-10-22T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-3-5-haiku-20241022",
            "display_name": "Claude Haiku 3.5",
            "created_at": "2024-10-22T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-3-5-sonnet-20240620",
            "display_name": "Claude Sonnet 3.5 (Old)",
            "created_at": "2024-06-20T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-3-haiku-20240307",
            "display_name": "Claude Haiku 3",
            "created_at": "2024-03-07T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-3-opus-20240229",
            "display_name": "Claude Opus 3",
            "created_at": "2024-02-29T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-3-sonnet-20240229",
            "display_name": "Claude Sonnet 3",
            "created_at": "2024-02-29T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-2.1",
            "display_name": "Claude 2.1",
            "created_at": "2023-11-21T00:00:00Z"
        },
        {
            "type": "model",
            "id": "claude-2.0",
            "display_name": "Claude 2.0",
            "created_at": "2023-07-11T00:00:00Z"
        }
    ]
}

@pytest.fixture
def provider():
    # Temporarily set API key for testing
    original_key = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["ANTHROPIC_API_KEY"] = "test_api_key"
    provider = AnthropicProvider()
    yield provider
    # Restore original key
    if original_key:
        os.environ["ANTHROPIC_API_KEY"] = original_key
    else:
        os.environ.pop("ANTHROPIC_API_KEY", None)

def test_provider_initialization_without_api_key():
    """Test that AnthropicProvider raises ValueError when API key is missing"""
    original_key = os.environ.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]
    
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY environment variable not set"):
        AnthropicProvider()
    
    # Restore original key
    if original_key:
        os.environ["ANTHROPIC_API_KEY"] = original_key

@responses.activate
def test_fetch_models_success(provider):
    """Test successful fetching of models from Anthropic API"""
    api_key = provider.api_key
    responses.add(
        responses.GET,
        "https://api.anthropic.com/v1/models",
        json=SAMPLE_MODELS_DATA,
        status=200
    )
    
    models = list(provider.fetch_models())
    
    assert len(models) == 11
    assert models[0]["id"] == "claude-opus-4-20250514"
    assert models[0]["display_name"] == "Claude Opus 4"
    assert models[0]["created_at"] == "2025-05-22T00:00:00Z"
    
    # Check headers
    assert responses.calls[0].request.headers["x-api-key"] == api_key
    assert responses.calls[0].request.headers["anthropic-version"] == "2023-06-01"

@responses.activate
def test_fetch_models_api_error(provider):
    """Test handling of API errors"""
    responses.add(
        responses.GET,
        "https://api.anthropic.com/v1/models",
        json={"error": {"message": "API error"}},
        status=500
    )
    
    with pytest.raises(requests.exceptions.HTTPError):
        provider.fetch_models()

@responses.activate
def test_fetch_models_empty_response(provider):
    """Test handling of empty response"""
    responses.add(
        responses.GET,
        "https://api.anthropic.com/v1/models",
        json={},  # No "data" field
        status=200
    )
    
    models = list(provider.fetch_models())
    assert len(models) == 0

def test_filter_public(provider):
    """Test that filter_public returns all models (no filtering for Anthropic)"""
    filtered = list(provider.filter_public(SAMPLE_MODELS_DATA["data"]))
    assert len(filtered) == 11
    assert filtered == SAMPLE_MODELS_DATA["data"]

def test_get_model_id(provider):
    """Test extraction of model ID"""
    model_record = {"id": "claude-3-opus-20240229"}
    assert provider.get_model_id(model_record) == "claude-3-opus-20240229"

def test_get_developer(provider):
    """Test that developer is always 'anthropic'"""
    assert provider.get_developer({}) == "anthropic"
    assert provider.get_developer({"owned_by": "someone-else"}) == "anthropic"

@pytest.mark.parametrize("model_data, expected_date_str", [
    # Valid ISO format dates
    ({"created_at": "2025-05-22T00:00:00Z"}, "2025-05-22"),
    ({"created_at": "2024-10-22T00:00:00Z"}, "2024-10-22"),
    ({"created_at": "2024-02-29T00:00:00Z"}, "2024-02-29"),  # Leap year
    ({"created_at": "2023-11-21T00:00:00Z"}, "2023-11-21"),
    
    # ISO format with timezone offset
    ({"created_at": "2024-03-07T12:30:00+00:00"}, "2024-03-07"),
    ({"created_at": "2024-03-07T12:30:00-05:00"}, "2024-03-07"),
    
    # Missing or invalid created_at
    ({}, "9999-12-31"),  # No created_at field
    ({"created_at": None}, "9999-12-31"),  # None value
    ({"created_at": "invalid-date"}, "9999-12-31"),  # Invalid format
    ({"created_at": ""}, "9999-12-31"),  # Empty string
    ({"created_at": "2024-13-01T00:00:00Z"}, "9999-12-31"),  # Invalid month
])
def test_get_release_date(provider, model_data, expected_date_str):
    """Test date parsing with various formats and edge cases"""
    expected = date.fromisoformat(expected_date_str)
    assert provider.get_release_date(model_data) == expected

def test_normalize(provider):
    """Test normalization of a model record to ModelEntry"""
    model_record = {
        "type": "model",
        "id": "claude-3-opus-20240229",
        "display_name": "Claude Opus 3",
        "created_at": "2024-02-29T00:00:00Z"
    }
    
    entry = provider.normalize(model_record)
    
    assert isinstance(entry, ModelEntry)
    assert entry.provider == "anthropic"
    assert entry.model_id == "claude-3-opus-20240229"
    assert entry.developer == "anthropic"
    assert entry.release_date == date(2024, 2, 29)
    assert entry.status == "active"

@responses.activate
def test_public_models(provider):
    """Test end-to-end public_models functionality"""
    responses.add(
        responses.GET,
        "https://api.anthropic.com/v1/models",
        json=SAMPLE_MODELS_DATA,
        status=200
    )
    
    with patch.object(provider, 'filter_public', wraps=provider.filter_public) as mock_filter_public, \
         patch.object(provider, 'normalize', wraps=provider.normalize) as mock_normalize:
        
        models = provider.public_models()
        
        # Check count
        assert len(models) == 11
        
        # Check all models are present
        expected_model_ids = [
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-5-sonnet-20240620",
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-2.1",
            "claude-2.0"
        ]
        
        model_ids = [m.model_id for m in models]
        for expected_id in expected_model_ids:
            assert expected_id in model_ids
        
        # Check methods were called
        assert mock_filter_public.called
        assert mock_normalize.call_count == 11
        
        # Check specific model details
        opus_4 = next(m for m in models if m.model_id == "claude-opus-4-20250514")
        assert opus_4.release_date == date(2025, 5, 22)
        assert opus_4.developer == "anthropic"
        assert opus_4.provider == "anthropic"
        assert opus_4.status == "active"
        
        # Check oldest model
        claude_2 = next(m for m in models if m.model_id == "claude-2.0")
        assert claude_2.release_date == date(2023, 7, 11)

@responses.activate
def test_retry_mechanism(provider):
    """Test that the retry decorator works for transient failures"""
    # First two calls fail, third succeeds
    responses.add(
        responses.GET,
        "https://api.anthropic.com/v1/models",
        json={"error": "Temporary failure"},
        status=503
    )
    responses.add(
        responses.GET,
        "https://api.anthropic.com/v1/models",
        json={"error": "Temporary failure"},
        status=503
    )
    responses.add(
        responses.GET,
        "https://api.anthropic.com/v1/models",
        json=SAMPLE_MODELS_DATA,
        status=200
    )
    
    models = list(provider.fetch_models())
    assert len(models) == 11
    assert len(responses.calls) == 3  # Verify it retried

def test_provider_slug(provider):
    """Test that the provider slug is correct"""
    assert provider.slug == "anthropic"
    assert AnthropicProvider.slug == "anthropic" 