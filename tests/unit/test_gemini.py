import os
import pytest
import responses
import requests
from datetime import date
from unittest.mock import patch

from model_registry.providers.gemini import GeminiProvider
from model_registry.schemas import ModelEntry
from dotenv import load_dotenv

load_dotenv()

# Sample API response data based on Gemini's models.list endpoint format
SAMPLE_MODELS_DATA_PAGE_1 = {
    "models": [
        {
            "name": "models/gemini-1.5-flash-001",
            "version": "001",
            "displayName": "Gemini 1.5 Flash 001",
            "description": "Fast and versatile performance",
            "inputTokenLimit": 2097152,
            "outputTokenLimit": 8192,
            "supportedGenerationMethods": ["generateContent", "countTokens"]
        },
        {
            "name": "models/gemini-1.5-flash-002", 
            "version": "002",
            "displayName": "Gemini 1.5 Flash 002",
            "description": "Fast and versatile performance",
            "inputTokenLimit": 2097152,
            "outputTokenLimit": 8192,
            "supportedGenerationMethods": ["generateContent", "countTokens"]
        },
        {
            "name": "models/gemini-1.5-flash-8b-20241119",
            "version": "20241119",
            "displayName": "Gemini 1.5 Flash 8B",
            "description": "Compact size with strong performance",
            "inputTokenLimit": 1048576,
            "outputTokenLimit": 8192,
            "supportedGenerationMethods": ["generateContent", "countTokens"]
        },
        {
            "name": "models/gemini-1.5-pro-20241022",
            "version": "20241022",
            "displayName": "Gemini 1.5 Pro",
            "description": "Advanced reasoning capabilities",
            "inputTokenLimit": 2097152,
            "outputTokenLimit": 8192,
            "supportedGenerationMethods": ["generateContent", "countTokens"]
        },
        {
            "name": "models/gemini-2.0-flash-20241210",
            "version": "20241210",
            "displayName": "Gemini 2.0 Flash",
            "description": "Next generation model",
            "inputTokenLimit": 1048576,
            "outputTokenLimit": 8192,
            "supportedGenerationMethods": ["generateContent", "countTokens"]
        }
    ],
    "nextPageToken": "page2token"
}

SAMPLE_MODELS_DATA_PAGE_2 = {
    "models": [
        {
            "name": "models/gemini-1.0-pro",
            "version": "001",
            "displayName": "Gemini 1.0 Pro",
            "description": "Balanced performance",
            "inputTokenLimit": 32768,
            "outputTokenLimit": 8192,
            "supportedGenerationMethods": ["generateContent"]
        },
        {
            "name": "models/gemini-1.0-pro-001",
            "version": "001",
            "displayName": "Gemini 1.0 Pro 001",
            "description": "Balanced performance",
            "inputTokenLimit": 32768,
            "outputTokenLimit": 8192,
            "supportedGenerationMethods": ["generateContent"]
        },
        {
            "name": "models/gemini-1.0-pro-vision-20240214",
            "version": "20240214",
            "displayName": "Gemini 1.0 Pro Vision",
            "description": "Multimodal understanding",
            "inputTokenLimit": 16384,
            "outputTokenLimit": 2048,
            "supportedGenerationMethods": ["generateContent"]
        },
        {
            "name": "models/text-embedding-004",
            "version": "004",
            "displayName": "Text Embedding 004",
            "description": "Text embeddings",
            "inputTokenLimit": 2048,
            "supportedGenerationMethods": ["embedContent"]
        },
        {
            "name": "models/model-without-date",
            "version": "001",
            "displayName": "Model Without Date",
            "description": "Test model without date",
            "inputTokenLimit": 8192,
            "outputTokenLimit": 2048,
            "supportedGenerationMethods": ["generateContent"]
        }
    ]
    # No nextPageToken means this is the last page
}

@pytest.fixture
def provider():
    # Temporarily set API key for testing
    original_key = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = "test_api_key"
    provider = GeminiProvider()
    yield provider
    # Restore original key
    if original_key:
        os.environ["GEMINI_API_KEY"] = original_key
    else:
        os.environ.pop("GEMINI_API_KEY", None)

def test_provider_initialization_without_api_key():
    """Test that GeminiProvider raises ValueError when API key is missing"""
    original_key = os.environ.get("GEMINI_API_KEY")
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
    
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable not set"):
        GeminiProvider()
    
    # Restore original key
    if original_key:
        os.environ["GEMINI_API_KEY"] = original_key

@responses.activate
def test_fetch_models_success_single_page(provider):
    """Test successful fetching of models from Gemini API with single page"""
    api_key = provider.api_key
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json={"models": SAMPLE_MODELS_DATA_PAGE_1["models"]},  # No nextPageToken
        status=200
    )
    
    models = list(provider.fetch_models())
    
    assert len(models) == 5
    assert models[0]["name"] == "models/gemini-1.5-flash-001"
    assert models[2]["name"] == "models/gemini-1.5-flash-8b-20241119"
    
    # Check URL parameters
    assert responses.calls[0].request.params["key"] == api_key
    assert responses.calls[0].request.params["pageSize"] == "100"

@responses.activate
def test_fetch_models_success_with_pagination(provider):
    """Test successful fetching of models with pagination"""
    api_key = provider.api_key
    
    # First page response
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json=SAMPLE_MODELS_DATA_PAGE_1,
        status=200
    )
    
    # Second page response
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json=SAMPLE_MODELS_DATA_PAGE_2,
        status=200
    )
    
    models = list(provider.fetch_models())
    
    # Should have all models from both pages
    assert len(models) == 10
    assert models[0]["name"] == "models/gemini-1.5-flash-001"
    assert models[5]["name"] == "models/gemini-1.0-pro"
    assert models[9]["name"] == "models/model-without-date"
    
    # Check that two requests were made
    assert len(responses.calls) == 2
    
    # Check first request
    assert responses.calls[0].request.params["key"] == api_key
    assert responses.calls[0].request.params["pageSize"] == "100"
    assert "pageToken" not in responses.calls[0].request.params
    
    # Check second request has pageToken
    assert responses.calls[1].request.params["key"] == api_key
    assert responses.calls[1].request.params["pageSize"] == "100"
    assert responses.calls[1].request.params["pageToken"] == "page2token"

@responses.activate
def test_fetch_models_api_error(provider):
    """Test handling of API errors"""
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json={"error": {"message": "API error", "code": 500}},
        status=500
    )
    
    with pytest.raises(requests.exceptions.HTTPError):
        provider.fetch_models()

@responses.activate
def test_fetch_models_partial_failure_during_pagination(provider):
    """Test that partial results are returned when pagination fails"""
    # First page succeeds
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json=SAMPLE_MODELS_DATA_PAGE_1,
        status=200
    )
    
    # Second page fails
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json={"error": {"message": "Server error"}},
        status=500
    )
    
    models = list(provider.fetch_models())
    
    # Should still return models from the first page
    assert len(models) == 5
    assert models[0]["name"] == "models/gemini-1.5-flash-001"

@responses.activate
def test_fetch_models_empty_response(provider):
    """Test handling of empty response"""
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json={},  # No "models" field
        status=200
    )
    
    models = list(provider.fetch_models())
    assert len(models) == 0

def test_filter_public(provider):
    """Test that filter_public returns all models (no filtering for Gemini)"""
    all_models = SAMPLE_MODELS_DATA_PAGE_1["models"] + SAMPLE_MODELS_DATA_PAGE_2["models"]
    filtered = list(provider.filter_public(all_models))
    assert len(filtered) == 10
    assert filtered == all_models

def test_get_model_id(provider):
    """Test extraction of model ID"""
    model_record = {"name": "models/gemini-1.5-flash-001"}
    assert provider.get_model_id(model_record) == "models/gemini-1.5-flash-001"
    
    # Test with missing name
    assert provider.get_model_id({}) == ""

def test_get_developer(provider):
    """Test that developer is always 'google'"""
    assert provider.get_developer({}) == "google"
    assert provider.get_developer({"owned_by": "someone-else"}) == "google"

@pytest.mark.parametrize("model_data, expected_date_str", [
    # Models with YYYYMMDD date suffix
    ({"name": "models/gemini-1.5-flash-8b-20241119"}, "2024-11-19"),
    ({"name": "models/gemini-1.5-pro-20241022"}, "2024-10-22"),
    ({"name": "models/gemini-2.0-flash-20241210"}, "2024-12-10"),
    ({"name": "models/gemini-1.0-pro-vision-20240214"}, "2024-02-14"),
    
    # Models without date suffix
    ({"name": "models/gemini-1.5-flash-001"}, "9999-12-31"),
    ({"name": "models/gemini-1.0-pro"}, "9999-12-31"),
    ({"name": "models/text-embedding-004"}, "9999-12-31"),
    ({"name": "models/model-without-date"}, "9999-12-31"),
    
    # Edge cases
    ({"name": ""}, "9999-12-31"),  # Empty name
    ({}, "9999-12-31"),  # Missing name
    ({"name": "models/model-20991231"}, "2099-12-31"),  # Future date
    ({"name": "models/model-20240229"}, "2024-02-29"),  # Leap year date
    ({"name": "models/model-20230230"}, "9999-12-31"),  # Invalid date (Feb 30)
    ({"name": "models/model-20241301"}, "9999-12-31"),  # Invalid month
    ({"name": "models/model-2024"}, "9999-12-31"),  # Incomplete date
    ({"name": "models/model-202412"}, "9999-12-31"),  # Incomplete date
])
def test_get_release_date(provider, model_data, expected_date_str):
    """Test date parsing with various formats and edge cases"""
    expected = date.fromisoformat(expected_date_str)
    assert provider.get_release_date(model_data) == expected

def test_normalize(provider):
    """Test normalization of a model record to ModelEntry"""
    model_record = {
        "name": "models/gemini-1.5-flash-8b-20241119",
        "version": "20241119",
        "displayName": "Gemini 1.5 Flash 8B",
        "description": "Compact size with strong performance",
        "inputTokenLimit": 1048576,
        "outputTokenLimit": 8192,
        "supportedGenerationMethods": ["generateContent", "countTokens"]
    }
    
    entry = provider.normalize(model_record)
    
    assert isinstance(entry, ModelEntry)
    assert entry.provider == "gemini"
    assert entry.model_id == "models/gemini-1.5-flash-8b-20241119"
    assert entry.developer == "google"
    assert entry.release_date == date(2024, 11, 19)
    assert entry.status == "active"

@responses.activate
def test_public_models(provider):
    """Test end-to-end public_models functionality"""
    # Set up paginated responses
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json=SAMPLE_MODELS_DATA_PAGE_1,
        status=200
    )
    
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json=SAMPLE_MODELS_DATA_PAGE_2,
        status=200
    )
    
    with patch.object(provider, 'filter_public', wraps=provider.filter_public) as mock_filter_public, \
         patch.object(provider, 'normalize', wraps=provider.normalize) as mock_normalize:
        
        models = provider.public_models()
        
        # Check count
        assert len(models) == 10
        
        # Check all models are present
        expected_model_ids = [
            "models/gemini-1.5-flash-001",
            "models/gemini-1.5-flash-002",
            "models/gemini-1.5-flash-8b-20241119",
            "models/gemini-1.5-pro-20241022",
            "models/gemini-2.0-flash-20241210",
            "models/gemini-1.0-pro",
            "models/gemini-1.0-pro-001",
            "models/gemini-1.0-pro-vision-20240214",
            "models/text-embedding-004",
            "models/model-without-date"
        ]
        
        model_ids = [m.model_id for m in models]
        for expected_id in expected_model_ids:
            assert expected_id in model_ids
        
        # Check methods were called
        assert mock_filter_public.called
        assert mock_normalize.call_count == 10
        
        # Check specific model details
        flash_8b = next(m for m in models if m.model_id == "models/gemini-1.5-flash-8b-20241119")
        assert flash_8b.release_date == date(2024, 11, 19)
        assert flash_8b.developer == "google"
        assert flash_8b.provider == "gemini"
        assert flash_8b.status == "active"
        
        # Check model without date
        no_date_model = next(m for m in models if m.model_id == "models/model-without-date")
        assert no_date_model.release_date == date(9999, 12, 31)

@responses.activate
def test_retry_mechanism(provider):
    """Test that the retry decorator works for transient failures"""
    # First two calls fail, third succeeds
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json={"error": "Temporary failure"},
        status=503
    )
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json={"error": "Temporary failure"},
        status=503
    )
    responses.add(
        responses.GET,
        f"https://generativelanguage.googleapis.com/v1beta/models",
        json={"models": SAMPLE_MODELS_DATA_PAGE_1["models"]},  # No pagination for simplicity
        status=200
    )
    
    models = list(provider.fetch_models())
    assert len(models) == 5
    assert len(responses.calls) == 3  # Verify it retried

def test_provider_slug(provider):
    """Test that the provider slug is correct"""
    assert provider.slug == "gemini"
    assert GeminiProvider.slug == "gemini" 