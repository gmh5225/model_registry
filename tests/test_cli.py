# Test for model_registry.main (CLI)
import pytest 
import json
import sys
import logging
from datetime import date
from pathlib import Path

from pydantic import ValidationError

# Assuming model_registry.main.main is the function to test
# and model_registry.main.MODELS_JSON_PATH is the path it uses.
from model_registry.main import main as cli_main
# from model_registry.main import PROVIDERS # To monkeypatch providers -> No longer global
from model_registry.schemas import ModelEntry
from model_registry.providers.base import Provider # For type hinting mock provider
from model_registry.providers.openai import OpenAIProvider # To specifically mock its methods


# Mock ModelEntry data
MOCK_MODEL_1_OPENAI = ModelEntry(provider="openai", model_id="gpt-4", release_date=date(2023, 3, 14), developer="openai")
MOCK_MODEL_2_OPENAI = ModelEntry(provider="openai", model_id="gpt-3.5-turbo", release_date=date(2022, 12, 1), developer="openai")
MOCK_MODEL_3_OTHER = ModelEntry(provider="another-provider", model_id="model-x", release_date=date(2024, 1, 1), developer="another-dev")

@pytest.fixture
def mock_openai_provider(monkeypatch):
    # Import the other providers here
    from model_registry.providers.anthropic import AnthropicProvider
    from model_registry.providers.gemini import GeminiProvider
    
    class MockOpenAIProviderBehaviors:
        _public_models_return_value = [MOCK_MODEL_1_OPENAI, MOCK_MODEL_2_OPENAI]
        _public_models_exception = None # New: store potential exception
        _slug_to_return = "openai" # Default slug

        def __init__(self): 
            self.api_key = "mock_api_key_for_testing"
            # logger.info(f"Mocked Provider initialized for slug {self.slug}")
            pass

        @property 
        def slug(self):
            return MockOpenAIProviderBehaviors._slug_to_return # Corrected access to class variable

        def public_models(self) -> list[ModelEntry]:
            if MockOpenAIProviderBehaviors._public_models_exception:
                raise MockOpenAIProviderBehaviors._public_models_exception
            return MockOpenAIProviderBehaviors._public_models_return_value

    monkeypatch.setattr(OpenAIProvider, "__init__", MockOpenAIProviderBehaviors.__init__)
    monkeypatch.setattr(OpenAIProvider, "public_models", MockOpenAIProviderBehaviors.public_models)
    monkeypatch.setattr(OpenAIProvider, "slug", MockOpenAIProviderBehaviors.slug) # Patch slug too
    
    # Reset class variables for each test run that uses this fixture
    MockOpenAIProviderBehaviors._public_models_return_value = [MOCK_MODEL_1_OPENAI, MOCK_MODEL_2_OPENAI]
    MockOpenAIProviderBehaviors._public_models_exception = None
    MockOpenAIProviderBehaviors._slug_to_return = "openai"

    # Also mock the other providers to return empty lists
    monkeypatch.setattr(AnthropicProvider, "__init__", lambda self: setattr(self, 'api_key', 'mock'))
    monkeypatch.setattr(AnthropicProvider, "public_models", lambda self: [])
    monkeypatch.setattr(AnthropicProvider, "slug", "anthropic")
    
    monkeypatch.setattr(GeminiProvider, "__init__", lambda self: setattr(self, 'api_key', 'mock'))
    monkeypatch.setattr(GeminiProvider, "public_models", lambda self: [])
    monkeypatch.setattr(GeminiProvider, "slug", "gemini")
    
    return MockOpenAIProviderBehaviors


@pytest.fixture(autouse=True)
def mock_sys_exit(monkeypatch):
    """Mock sys.exit to prevent test termination and capture exit code."""
    mock_exit = lambda code=0: setattr(sys, "_last_exit_code", code)
    monkeypatch.setattr(sys, "exit", mock_exit)
    # Ensure _last_exit_code is reset for each test
    if hasattr(sys, "_last_exit_code"):
        delattr(sys, "_last_exit_code")

def run_cli(tmp_path, monkeypatch, initial_models_json_content=None, mock_provider_behaviors=None):
    """Helper to run the CLI main function with mocks."""
    test_models_json = tmp_path / "models.json"
    monkeypatch.setattr("model_registry.main.MODELS_JSON_PATH", test_models_json)

    if initial_models_json_content is not None:
        with open(test_models_json, 'w') as f:
            json.dump(initial_models_json_content, f, indent=2)

    # Provider mocking is now handled by fixtures that patch the provider classes themselves.
    # If mock_provider_behaviors is provided, it implies we want to change the default behavior
    # set up by mock_openai_provider fixture.
    if mock_provider_behaviors:
        # This assumes mock_provider_behaviors is a dictionary like:
        # { "OpenAIProvider": { "public_models": lambda: [some_models] } }
        # Or that it directly sets class attributes on the behavior class from the fixture
        pass # Further refinement needed if tests need more complex provider setups

    cli_main()
    
    exit_code = getattr(sys, "_last_exit_code", None)
    return test_models_json, exit_code


def test_cli_no_existing_file(tmp_path, monkeypatch, capsys, mock_openai_provider):
    """Test CLI run when models.json does not exist."""
    
    # Configure mock_openai_provider to return specific models for this test
    mock_openai_provider._public_models_return_value = [MOCK_MODEL_1_OPENAI]
    # Ensure the mock provider is the one used - this is now handled by the fixture patching OpenAIProvider class

    models_json_file, exit_code = run_cli(tmp_path, monkeypatch)

    assert exit_code == 0
    assert models_json_file.exists()
    with open(models_json_file, 'r') as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["model_id"] == MOCK_MODEL_1_OPENAI.model_id
    
    captured = capsys.readouterr()
    assert f"{models_json_file} updated with 1 models." in captured.out

def test_cli_no_diff(tmp_path, monkeypatch, capsys, mock_openai_provider):
    """Test CLI run when fetched models match existing models.json."""
    initial_content = [MOCK_MODEL_1_OPENAI.model_dump(mode='json')]
    
    mock_openai_provider._public_models_return_value = [MOCK_MODEL_1_OPENAI]

    models_json_file, exit_code = run_cli(tmp_path, monkeypatch, initial_models_json_content=initial_content)

    assert exit_code == 0
    assert models_json_file.exists() # File should still exist
    
    # Check that the content hasn't changed (by re-reading and comparing, or by mtime if precise)
    with open(models_json_file, 'r') as f:
        data = json.load(f)
    assert data == initial_content # Content should be identical
    
    captured = capsys.readouterr()
    assert f"No content changes to {models_json_file}" in captured.out

def test_cli_with_diff_new_models_added(tmp_path, monkeypatch, capsys, mock_openai_provider):
    """Test CLI adds new models to an existing models.json."""
    initial_content = [MOCK_MODEL_1_OPENAI.model_dump(mode='json')]
    
    # mock_openai_provider will return model1 and model2
    mock_openai_provider._public_models_return_value = [MOCK_MODEL_1_OPENAI, MOCK_MODEL_2_OPENAI]

    models_json_file, exit_code = run_cli(tmp_path, monkeypatch, initial_models_json_content=initial_content)

    assert exit_code == 0
    assert models_json_file.exists()
    with open(models_json_file, 'r') as f:
        data = json.load(f)
    
    assert len(data) == 2 # Model 1 (existing) + Model 2 (new)
    model_ids_in_file = {item["model_id"] for item in data}
    assert MOCK_MODEL_1_OPENAI.model_id in model_ids_in_file
    assert MOCK_MODEL_2_OPENAI.model_id in model_ids_in_file
    
    captured = capsys.readouterr()
    assert f"{models_json_file} updated with 2 models." in captured.out

def test_cli_failing_provider(tmp_path, monkeypatch, capsys, caplog, mock_openai_provider):
    """Test CLI handles a provider failing gracefully."""
    
    # Configure the mock behavior for OpenAIProvider to fail
    mock_openai_provider._public_models_exception = ConnectionError("Simulated network failure from mocked OpenAIProvider")
    mock_openai_provider._slug_to_return = "failing-openai" # Change slug for the log message

    # Since main.py only instantiates OpenAIProvider, we simulate failure by making its mock fail.
    # No initial content, so if this failing provider is the only one, models.json should be empty or not created.
    # However, the current main.py logic will try to save an empty list if all providers fail.

    models_json_file, exit_code = run_cli(tmp_path, monkeypatch)

    assert exit_code == 0 # CLI should still exit 0 even if providers fail, but writes empty/no-change file
    
    # What should happen if ALL providers fail? 
    # main.py currently would write an empty models.json if it didn't exist,
    # or print "no changes" if models.json was already empty.
    # Let's assume for this test, models.json gets created (or remains) empty.
    assert models_json_file.exists()
    with open(models_json_file, 'r') as f:
        data = json.load(f)
    assert len(data) == 0 # No models should be successfully fetched
    
    captured_stdout = capsys.readouterr().out
    # Depending on main.py logic for empty results + no pre-existing file:
    assert f"{models_json_file} updated with 0 models." in captured_stdout 
    # OR if it prints "no changes" for an empty new file vs no file, that needs checking.

    assert any(
        ("Failed to fetch models from failing-openai" in record.message and
         "Simulated network failure" in record.message and 
         record.levelname == "ERROR")
        for record in caplog.records
    )

def test_cli_model_sorting_and_content(tmp_path, monkeypatch, capsys, mock_openai_provider):
    """Test that models.json content is sorted correctly."""
    # Models are MOCK_MODEL_2_OPENAI (gpt-3.5-turbo) and MOCK_MODEL_1_OPENAI (gpt-4)
    # Expected sorted order: gpt-3.5-turbo, then gpt-4 (based on model_id string sort)
    
    # mock_openai_provider returns them in a specific order (M1 then M2)
    # but main.py sorts them as (model_id, developer, provider)
    # MOCK_MODEL_1_OPENAI.model_id = "gpt-4"
    # MOCK_MODEL_2_OPENAI.model_id = "gpt-3.5-turbo"
    # So, "gpt-3.5-turbo" should come before "gpt-4"
    
    mock_openai_provider._public_models_return_value = [MOCK_MODEL_1_OPENAI, MOCK_MODEL_2_OPENAI]

    models_json_file, exit_code = run_cli(tmp_path, monkeypatch)

    assert exit_code == 0
    assert models_json_file.exists()
    with open(models_json_file, 'r') as f:
        data = json.load(f)
    
    assert len(data) == 2
    assert data[0]["model_id"] == MOCK_MODEL_2_OPENAI.model_id # gpt-3.5-turbo
    assert data[0]["provider"] == MOCK_MODEL_2_OPENAI.provider
    assert data[1]["model_id"] == MOCK_MODEL_1_OPENAI.model_id # gpt-4
    assert data[1]["provider"] == MOCK_MODEL_1_OPENAI.provider

    captured = capsys.readouterr()
    assert f"{models_json_file} updated with 2 models." in captured.out

def test_cli_preserves_existing_models_on_new_fetch(tmp_path, monkeypatch, capsys, mock_all_providers):
    """Test CLI preserves existing models not in current fetch, and adds new ones."""
    mock_openai_provider, MockAnthropicProviderBehaviors, MockGeminiProviderBehaviors = mock_all_providers
    
    # Existing model in file is MOCK_MODEL_3_OTHER
    initial_content = [MOCK_MODEL_3_OTHER.model_dump(mode='json')]
    
    # mock_openai_provider will return MOCK_MODEL_1_OPENAI
    mock_openai_provider._public_models_return_value = [MOCK_MODEL_1_OPENAI]

    models_json_file, exit_code = run_cli(tmp_path, monkeypatch, initial_models_json_content=initial_content)

    assert exit_code == 0
    assert models_json_file.exists()
    with open(models_json_file, 'r') as f:
        data = json.load(f)
    
    assert len(data) == 2 # Existing MOCK_MODEL_3_OTHER + new MOCK_MODEL_1_OPENAI
    model_ids_in_file = {item["model_id"] for item in data}
    assert MOCK_MODEL_3_OTHER.model_id in model_ids_in_file
    assert MOCK_MODEL_1_OPENAI.model_id in model_ids_in_file
    
    # Check sorting: MOCK_MODEL_3_OTHER (model-x), MOCK_MODEL_1_OPENAI (gpt-4)
    # "model-x" comes before "gpt-4" alphabetically
    assert data[0]["model_id"] == MOCK_MODEL_3_OTHER.model_id  # model-x
    assert data[1]["model_id"] == MOCK_MODEL_1_OPENAI.model_id  # gpt-4
    
    captured = capsys.readouterr()
    assert f"{models_json_file} updated with 2 models." in captured.out

def test_cli_empty_fetch_from_provider(tmp_path, monkeypatch, capsys, mock_openai_provider):
    """Test CLI when a provider returns an empty list of models."""
    initial_content = [MOCK_MODEL_1_OPENAI.model_dump(mode='json')]
    
    mock_openai_provider._public_models_return_value = [] # Provider returns no models

    models_json_file, exit_code = run_cli(tmp_path, monkeypatch, initial_models_json_content=initial_content)

    assert exit_code == 0 # No changes, so exit 0
    
    with open(models_json_file, 'r') as f:
        data = json.load(f)
    assert len(data) == 1 # Should still contain the initial model
    assert data[0]["model_id"] == MOCK_MODEL_1_OPENAI.model_id
        
    captured = capsys.readouterr()
    # Because no new models were added and the existing content is the same as what would be written
    assert f"No content changes to {models_json_file}" in captured.out
    
    # Check log for "No models returned"
    # To do this properly, we'd need to capture log output.
    # For now, focusing on CLI output and file state.
    # If using caplog:
    # assert "No models returned from openai." in caplog.text

@pytest.fixture
def mock_all_providers(monkeypatch, mock_openai_provider):
    """Mock all providers to prevent real API calls during tests."""
    
    # Mock AnthropicProvider
    class MockAnthropicProviderBehaviors:
        def __init__(self):
            self.api_key = "mock_anthropic_api_key"
            pass
        
        @property
        def slug(self):
            return "anthropic"
        
        def public_models(self) -> list[ModelEntry]:
            # Return empty list or specific test models if needed
            return []
    
    # Mock GeminiProvider  
    class MockGeminiProviderBehaviors:
        def __init__(self):
            self.api_key = "mock_gemini_api_key"
            pass
        
        @property
        def slug(self):
            return "gemini"
        
        def public_models(self) -> list[ModelEntry]:
            # Return empty list or specific test models if needed
            return []
    
    # Import the providers to patch them
    from model_registry.providers.anthropic import AnthropicProvider
    from model_registry.providers.gemini import GeminiProvider
    
    # Patch AnthropicProvider
    monkeypatch.setattr(AnthropicProvider, "__init__", MockAnthropicProviderBehaviors.__init__)
    monkeypatch.setattr(AnthropicProvider, "public_models", MockAnthropicProviderBehaviors.public_models)
    monkeypatch.setattr(AnthropicProvider, "slug", MockAnthropicProviderBehaviors.slug)
    
    # Patch GeminiProvider
    monkeypatch.setattr(GeminiProvider, "__init__", MockGeminiProviderBehaviors.__init__)
    monkeypatch.setattr(GeminiProvider, "public_models", MockGeminiProviderBehaviors.public_models)
    monkeypatch.setattr(GeminiProvider, "slug", MockGeminiProviderBehaviors.slug)
    
    return (mock_openai_provider, MockAnthropicProviderBehaviors, MockGeminiProviderBehaviors)
