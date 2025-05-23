import json
import subprocess
from pathlib import Path
import pytest

from model_registry.main import main as cli_main
from model_registry.providers.openai import OpenAIProvider
from model_registry.providers.anthropic import AnthropicProvider
from model_registry.providers.gemini import GeminiProvider
from model_registry.schemas import ModelEntry


# Dummy model entries for testing
# We'll need at least two distinct sets to simulate two providers
DUMMY_MODELS_PROVIDER_A = [
    ModelEntry(provider="provider_a", model_id="model_a1", release_date="2023-01-01", developer="dev_a", status="active"),
    ModelEntry(provider="provider_a", model_id="model_a2", release_date="2023-01-15", developer="dev_a", status="active"),
]

DUMMY_MODELS_PROVIDER_B = [
    ModelEntry(provider="provider_b", model_id="model_b1", release_date="2023-02-01", developer="dev_b", status="deprecated"),
]

ALL_EXPECTED_MODELS_SORTED = sorted(
    [model.model_dump(mode='json') for model in DUMMY_MODELS_PROVIDER_A + DUMMY_MODELS_PROVIDER_B],
    key=lambda x: (x['provider'], x['developer'], x['model_id'])
)


def mock_provider_a_public_models():
    return DUMMY_MODELS_PROVIDER_A

def mock_provider_b_public_models():
    return DUMMY_MODELS_PROVIDER_B

def test_integration_cli_updates_and_no_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """
    Tests the CLI's ability to:
    1. Create models.json with combined data from providers.
    2. Detect no changes on a subsequent run.
    """
    
    # Mock all three providers that main.py instantiates
    
    # Mock behavior for OpenAIProvider - returns DUMMY_MODELS_PROVIDER_A
    class MockOpenAIBehavior:
        def __init__(self):
            self.api_key = "mock_api_key"
            pass
        
        @property
        def slug(self):
            return "openai"
        
        def public_models(self):
            return DUMMY_MODELS_PROVIDER_A
    
    # Mock behavior for AnthropicProvider - returns DUMMY_MODELS_PROVIDER_B
    class MockAnthropicBehavior:
        def __init__(self):
            self.api_key = "mock_api_key"
            pass
        
        @property
        def slug(self):
            return "anthropic"
        
        def public_models(self):
            return DUMMY_MODELS_PROVIDER_B
    
    # Mock behavior for GeminiProvider - returns empty list
    class MockGeminiBehavior:
        def __init__(self):
            self.api_key = "mock_api_key"
            pass
        
        @property
        def slug(self):
            return "gemini"
        
        def public_models(self):
            return []  # Gemini returns no models for this test
    
    # Store original methods for restoration later
    original_openai_init = OpenAIProvider.__init__
    original_openai_public_models = OpenAIProvider.public_models
    original_openai_slug = getattr(OpenAIProvider, "slug", None)
    
    original_anthropic_init = AnthropicProvider.__init__
    original_anthropic_public_models = AnthropicProvider.public_models
    original_anthropic_slug = getattr(AnthropicProvider, "slug", None)
    
    original_gemini_init = GeminiProvider.__init__
    original_gemini_public_models = GeminiProvider.public_models
    original_gemini_slug = getattr(GeminiProvider, "slug", None)
    
    # Apply patches
    monkeypatch.setattr(OpenAIProvider, "__init__", MockOpenAIBehavior.__init__)
    monkeypatch.setattr(OpenAIProvider, "public_models", MockOpenAIBehavior.public_models)
    monkeypatch.setattr(OpenAIProvider, "slug", MockOpenAIBehavior.slug)
    
    monkeypatch.setattr(AnthropicProvider, "__init__", MockAnthropicBehavior.__init__)
    monkeypatch.setattr(AnthropicProvider, "public_models", MockAnthropicBehavior.public_models)
    monkeypatch.setattr(AnthropicProvider, "slug", MockAnthropicBehavior.slug)
    
    monkeypatch.setattr(GeminiProvider, "__init__", MockGeminiBehavior.__init__)
    monkeypatch.setattr(GeminiProvider, "public_models", MockGeminiBehavior.public_models)
    monkeypatch.setattr(GeminiProvider, "slug", MockGeminiBehavior.slug)
    
    models_json_path = tmp_path / "models.json"
    monkeypatch.setattr("model_registry.main.MODELS_JSON_PATH", models_json_path)
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)

    # First run: Create models.json
    # We need to ensure the CLI runs in the context of tmp_path for models.json
    # The CLI should write to models.json in the current working directory.
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path) # Make CLI write to tmp_path/models.json


    # Run the CLI main function
    # Option 1: Call the main function directly
    # We need to handle sys.argv if main() parses it, or ensure it doesn't for this test.
    # For now, assume main() doesn't need special argv.
    
    # Initial run - should create models.json
    with pytest.raises(SystemExit) as e:
        cli_main()
    assert e.type == SystemExit
    assert e.value.code == 0
    
    captured = capsys.readouterr()
    
    assert models_json_path.exists(), "models.json was not created"
    
    with open(models_json_path, "r") as f:
        content = json.load(f)
    
    assert content == ALL_EXPECTED_MODELS_SORTED, "models.json content does not match expected"

    # Second run: Should detect no changes
    # Note: The mocked OpenAIProvider methods are still patched from the first run.
    with pytest.raises(SystemExit) as e_second:
        cli_main()
    assert e_second.type == SystemExit
    assert e_second.value.code == 0
    captured_second_run = capsys.readouterr()
    
    assert captured_second_run.out.startswith("No content changes to "), "CLI did not detect 'no changes' on second run"

    # Restore original OpenAIProvider methods
    monkeypatch.setattr(OpenAIProvider, "__init__", original_openai_init)
    monkeypatch.setattr(OpenAIProvider, "public_models", original_openai_public_models)
    if original_openai_slug:
        monkeypatch.setattr(OpenAIProvider, "slug", original_openai_slug)

    # Restore original AnthropicProvider methods
    monkeypatch.setattr(AnthropicProvider, "__init__", original_anthropic_init)
    monkeypatch.setattr(AnthropicProvider, "public_models", original_anthropic_public_models)
    if original_anthropic_slug:
        monkeypatch.setattr(AnthropicProvider, "slug", original_anthropic_slug)

    # Restore original GeminiProvider methods
    monkeypatch.setattr(GeminiProvider, "__init__", original_gemini_init)
    monkeypatch.setattr(GeminiProvider, "public_models", original_gemini_public_models)
    if original_gemini_slug:
        monkeypatch.setattr(GeminiProvider, "slug", original_gemini_slug)

    # Alternative: Running as a subprocess
    # This can be more robust as it's closer to how the user/CI would run it.
    # cwd_for_subprocess = str(tmp_path)
    # env_for_subprocess = os.environ.copy()
    # # Potentially add OPENAI_API_KEY etc. to env_for_subprocess if needed by actual providers
    
    # # First run
    # result_first_run = subprocess.run(
    #     ["python", "-m", "model_registry.main"],
    #     cwd=cwd_for_subprocess,
    #     capture_output=True,
    #     text=True,
    #     env=env_for_subprocess
    # )
    # print("Subprocess First run stdout:", result_first_run.stdout)
    # print("Subprocess First run stderr:", result_first_run.stderr)
    # assert result_first_run.returncode == 0
    # assert models_json_path.exists()
    # with open(models_json_path, "r") as f:
    #     content_subprocess = json.load(f)
    # assert content_subprocess == ALL_EXPECTED_MODELS_SORTED

    # # Second run
    # result_second_run = subprocess.run(
    #     ["python", "-m", "model_registry.main"],
    #     cwd=cwd_for_subprocess,
    #     capture_output=True,
    #     text=True,
    #     env=env_for_subprocess
    # )
    # print("Subprocess Second run stdout:", result_second_run.stdout)
    # print("Subprocess Second run stderr:", result_second_run.stderr)
    # assert result_second_run.returncode == 0
    # assert "No changes to models.json" in result_second_run.stdout

    # The direct cli_main() call is generally preferred for unit/integration tests
    # if it can be made to work cleanly (handling cwd, argv, exit codes).
    # Subprocess is good for true end-to-end or if the script has complex setup
    # not easily replicable by direct function call.

    # Current implementation uses direct cli_main() call.
    # Note: The `monkeypatch.setattr("pathlib.Path.cwd", ...)` is a common way to control
    # where file operations happen relative to. The main script should use `Path.cwd()` or
    # relative paths for this to be effective. If it uses `os.getcwd()`, then
    # `monkeypatch.setattr("os.getcwd", ...)` would be needed.
    # Or, if `models.json` path is hardcoded or taken from an arg, that would need patching.
    # Based on M5, it seems to write to `models.json` at repo root, which implies it might
    # use a relative path from cwd.

    # Need to ensure `dotenv.load_dotenv()` in `main.py` doesn't cause issues if `.env` is not present
    # or if it tries to load API keys that aren't needed for these mocked providers.
    # The provided solution uses `pytest.MonkeyPatch.setattr` on `model_registry.main.PROVIDERS`. This is the most direct way if `PROVIDERS` is a global or module-level list in `main.py`.
    # If providers are instantiated inside the main function, the patching strategy would need to change (e.g., patch the provider classes themselves or the function that instantiates them). 