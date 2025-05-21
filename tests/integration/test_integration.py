import json
import subprocess
from pathlib import Path
import pytest

from model_registry.main import main as cli_main
from model_registry.providers.openai import OpenAIProvider
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
    # Patch the PROVIDERS list in main.py and their public_models methods
    # This requires knowing the structure of main.PROVIDERS or finding a way to inject them.
    # For now, let's assume we can patch the specific provider instances if they are accessible,
    # or patch a factory/function that yields them.

    # A more robust way would be to patch where PROVIDERS are defined or imported.
    # If PROVIDERS is `[OpenAIProvider(), AnthropicProvider()]`
    # we need to patch `OpenAIProvider.public_models` and `AnthropicProvider.public_models`
    # For this example, let's assume `model_registry.main.PROVIDERS` can be patched.
    
    # Mocking provider imports if they are directly used in main
    # This is highly dependent on how main.py imports and uses providers.
    # We'll assume a simplified scenario first.

    # Scenario: main.py dynamically instantiates providers based on a list of classes
    # or directly has instances. We need to find where `OpenAIProvider` (and potentially others)
    # is used and patch its `public_models` method.

    # Let's assume main.py looks something like:
    # from model_registry.providers.openai import OpenAIProvider
    # from model_registry.providers.anthropic import AnthropicProvider # If it exists
    # PROVIDERS = [OpenAIProvider(), AnthropicProvider()]
    # We would then:
    # monkeypatch.setattr("model_registry.providers.openai.OpenAIProvider.public_models", mock_provider_a_public_models)
    # monkeypatch.setattr("model_registry.providers.anthropic.AnthropicProvider.public_models", mock_provider_b_public_models)
    # And then patch main.PROVIDERS to only include these mocked versions or ensure only these are called.

    # For a start, let's try to patch the `public_models` method of a known provider.
    # This might require knowing which providers are active.
    # From todo.md, OpenAIProvider is implemented. Anthropic is planned.
    # Let's assume only OpenAIProvider is currently in main.PROVIDERS for simplicity of this first pass.
    
    # We need to find out how PROVIDERS is structured in `src/model_registry/main.py`.
    # For now, we'll proceed with a placeholder for provider patching.
    
    # Placeholder for actual patching - this will be refined after inspecting main.py
    # For now, let's assume we can directly patch a list of provider instances in `main.py`
    
    class MockProviderBehavior:
        # This will define the behavior for ONE of the providers main.py instantiates.
        # If main.py instantiates multiple types, we need a more complex setup.
        # For now, main.py does: providers = [OpenAIProvider()]
        # So, we will patch OpenAIProvider.

        _public_models_return_value = []
        _slug = "default-mocked-slug"

        def __init__(self): # Mocked __init__ for the patched provider class
            # self.api_key = "mock_api_key_for_integration_test"
            pass # No actual init logic needed for these mocks normally

        @property
        def slug(self):
            return MockProviderBehavior._slug

        def public_models(self):
            return MockProviderBehavior._public_models_return_value
        
        # def init(self): # No longer needed
        #     pass

    # Create two distinct behavior sets for two "virtual" providers
    # main.py only creates OpenAIProvider. To simulate two providers, we'd have to make main.py create two,
    # or make one OpenAIProvider instance somehow return combined data, which is not ideal for this test.

    # Simplification: Assume main.py is modified for the test to instantiate two distinct mockable providers, 
    # or we use a more advanced patching technique to make it seem like it does.
    # For now, let's assume main.py is `providers = [PatchedProvider1(), PatchedProvider2()]`
    # This is a bit of a leap. The current main.py is `providers = [OpenAIProvider()]`
    # Let's adjust to patch OpenAIProvider, and have its mock return *all* models for the test.

    # Store original OpenAIProvider methods
    original_openai_init = OpenAIProvider.__init__
    original_openai_public_models = OpenAIProvider.public_models
    original_openai_slug_descriptor = getattr(OpenAIProvider, "slug", None) # slug might be class var or property

    # Define the combined behavior for the single OpenAIProvider instance main.py will create
    MockProviderBehavior._public_models_return_value = DUMMY_MODELS_PROVIDER_A + DUMMY_MODELS_PROVIDER_B
    MockProviderBehavior._slug = "mocked-openai-for-integration"

    monkeypatch.setattr(OpenAIProvider, "__init__", MockProviderBehavior.__init__)
    monkeypatch.setattr(OpenAIProvider, "public_models", MockProviderBehavior.public_models)
    # If OpenAIProvider.slug is a simple class attribute, this works.
    # If it's a property, monkeypatch.setattr(OpenAIProvider, "slug", MockProviderBehavior.slug) is better.
    # Let's assume it could be a property for safety, though current Provider base has it as class attr.
    monkeypatch.setattr(OpenAIProvider, "slug", MockProviderBehavior.slug) # Patch as property

    # mock_provider_instance_a = MockProvider(DUMMY_MODELS_PROVIDER_A, slug="provider_a")
    # mock_provider_instance_b = MockProvider(DUMMY_MODELS_PROVIDER_B, slug="provider_b")

    # Assuming main.py has a list `PROVIDERS`
    # monkeypatch.setattr("model_registry.main.PROVIDERS", [mock_provider_instance_a, mock_provider_instance_b]) # Old way

    models_json_path = tmp_path / "models.json"
    # Also patch the MODELS_JSON_PATH global in main.py to use the temporary path
    monkeypatch.setattr("model_registry.main.MODELS_JSON_PATH", models_json_path)

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
    if original_openai_slug_descriptor:
        monkeypatch.setattr(OpenAIProvider, "slug", original_openai_slug_descriptor)
    else: # If it was a simple attribute and not a descriptor, it might have been overwritten
        # This part of restoration is tricky if slug was a simple class variable overwritten by a property.
        # For now, if OpenAIProvider.slug was just `slug = "openai"`, this simple del might not be enough
        # or could error if the property patch made it non-deletable. A more robust restore might be needed
        # if tests run after this one rely on the original slug.
        # Given it's likely a class variable set in the class definition, it should be fine.
        pass 

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