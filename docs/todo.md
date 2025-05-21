# 📋 TODO Checklist — Public LLM Model Registry

Use this as your master tick-list from first commit to production.  
Tasks are grouped by milestone; every item is an atomic, test-backed step.

---

## M1 – Initial Scaffolding & Tooling
- [x] **Task 1: Create repo root with `.gitignore`, `README.md` stub**
  - [x] Initialize Git repository (`git init`).
  - [x] Create a basic `README.md` stub.
  - [x] Create `.gitignore` file (for Python, venv, `__pycache__`, common OS files).
- [x] **Task 2: Add `pyproject.toml` and initial source directory**
  - [x] Create `pyproject.toml` with:
    - Project name "model_registry", version "0.1.0", basic description.
    - Build-system: `requires = ["uv"]`, `build-backend = "uv"`. (Assuming `uv` is the build system based on spec mentions for installing; adjust if `setuptools` or `flit` etc. are used for backend)
    - Python version requirement (e.g., `requires-python = ">=3.11"`).
    - Dependencies block initially empty.
  - [x] Create `src/model_registry/__init__.py`.
- [x] **Task 3: Create `.env.example` (placeholders only)**
  - [x] File content:
    - `OPENAI_API_KEY=""`
    - `ANTHROPIC_API_KEY=""`
- [x] **Task 4: Commit initial layout**
  - [x] Commit with message like "chore: initial scaffolding".

---

## M2 – Data Schema & Core Utilities
- [x] **Task 5: Install `pydantic`**
  - [x] Add `pydantic` to `pyproject.toml` dependencies.
  - [x] Run `uv pip install pydantic`.
- [x] **Task 6: Implement `src/model_registry/schemas.py` with `ModelEntry`**
  - [x] Define `ModelEntry(BaseModel)` with fields:
    - `provider: str`
    - `model_id: str` (ensure non-empty, e.g., using `pydantic.constr(min_length=1)`)
    - `release_date: date` (from `datetime`)
    - `developer: str`
    - `status: str = "active"` (e.g., "active", "deprecated")
- [x] **Task 7: Add unit tests for `schemas.py` (in `tests/test_schema.py`)**
  - [x] Test that a valid `ModelEntry` instance passes validation.
  - [x] Test that missing required fields or empty `model_id` raise `pydantic.ValidationError`.
  - [x] Test that a non-ISO format string for `release_date` raises `pydantic.ValidationError`.
  - [x] Test `status` field defaults and accepts valid values.
- [x] **Task 8: Add central logging setup (`src/model_registry/logger.py`)**
  - [x] Implement a basic logging configuration (e.g., to console).
  - [x] Initialize logger in `src/model_registry/__init__.py`.
- [X] **Commit "feat: data schema, logging & tests"**

---

## M3 – Provider Framework
- [x] **Task 9: Create `src/model_registry/providers/base.py`**
  - [x] Define abstract class `Provider(ABC)`:
    - Class attribute `slug: str`.
    - Abstract method `fetch_models(self) -> Iterable[Dict[str, Any]]`.
    - Abstract method `filter_public(self, raw: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]`.
    - Abstract method `get_model_id(self, model_record: Dict[str, Any]) -> str`.
    - Abstract method `get_developer(self, model_record: Dict[str, Any]) -> str`.
    - Abstract method `get_release_date(self, model_record: Dict[str, Any]) -> date`.
    - Method `normalize(self, model_record: Dict[str, Any]) -> ModelEntry`.
    - Method `public_models(self) -> list[ModelEntry]`.
  - [x] Implement a simple retry decorator (e.g., 3 attempts, exponential backoff) for provider methods that make network calls.
- [x] **Task 10: Unit test for `providers/base.py` (in `tests/unit/test_provider_base.py`)**
  - [x] Create a `DummyProvider(Provider)` subclass.
  - [x] Test that `public_models()` correctly processes and returns mocked data.
  - [x] Test the retry decorator logic (if feasible in isolation).
- [X] **Commit "feat: provider base"**

---

## M4 – OpenAI Provider
- [x] **Task 11: Add `requests` dependency**
  - [x] Add `requests` to `pyproject.toml` dependencies.
  - [x] Run `uv pip install requests`.
- [x] **Task 12: Implement `src/model_registry/providers/openai.py`**
  - [x] Define `OpenAIProvider(Provider)` with `slug = "openai"`.
  - [x] `fetch_models()`:
    - GET `https://api.openai.com/v1/models`.
    - Use `OPENAI_API_KEY` environment variable for `Authorization` header.
    - Apply retry decorator.
  - [x] `filter_public()`: Keep records where `owned_by == "openai"` and ID does not contain `":ft:"`.
  - [x] `get_developer()`: Return `"openai"`.
  - [x] `get_release_date()`: Parse date string (`%Y-%m-%d`) from model ID if present; otherwise, fallback to default future timestamp.
- [x] **Task 13: Unit tests for `openai.py` (in `tests/unit/test_openai.py`)**
  - [x] Use `responses` library (add to dev dependencies) to mock HTTP calls to `/v1/models`.
  - [x] Test `fetch_models()` including API key handling.
  - [x] Test `filter_public()` logic (e.g., fine-tuned models are excluded, only OpenAI models included).
  - [x] Test `get_release_date()` logic with various ID formats and fallback.
  - [x] Test `normalize()` and `public_models()` for overall correctness.
- [ ] **Commit "feat: OpenAI provider"**

---

## M5 – Registry CLI
- [x] **Task 17: Implement `src/model_registry/main.py`**
  - [x] Add `python-dotenv` to `pyproject.toml` (dev or optional dependency).
  - [x] Load environment variables using `dotenv.load_dotenv()` for local development.
  - [x] Define a list of provider instances (e.g., `PROVIDERS = [OpenAIProvider()]`).
  - [x] Main function to:
    - [x] Iterate through `PROVIDERS`, call `public_models()` on each, and handle potential errors gracefully (log and skip provider).
    - [x] Aggregate all `ModelEntry` objects into a single list.
    - [x] Convert the list of `ModelEntry` objects to a list of dictionaries (`[model.model_dump(mode='json') for model in all_models]`).
    - [x] Sort the list of models (by `id`, then `developer`, then `provider`) for consistent output.
    - [x] Serialize the sorted list to a JSON string with indent 2.
  - [x] Compare the new JSON (e.g., by comparing a hash of the sorted list's JSON string) with the content of `models.json` (if it exists at repo root).
    - [x] If identical: print "No changes to `models.json`." and exit 0.
    - [x] If different (or file doesn't exist): write the new JSON string to `models.json`, print a summary (e.g., "models.json updated."), and exit 0.
  - [x] Add CLI entrypoint (e.g., using `if __name__ == "__main__:"`) to allow running via `python -m model_registry.main`.
- [x] **Task 18: Unit tests for `main.py` (in `tests/test_cli.py`)**
  - [x] Use `pytest.MonkeyPatch` and `tmp_path` fixture.
  - [x] Patch provider `public_models()` methods to return controlled data.
  - [x] Test "no diff" case: CLI runs, `models.json` is not written if content (hash) is the same, exit code 0.
  - [x] Test "diff" case: CLI runs, `models.json` is overwritten with new content, exit code 0.
  - [x] Test "no existing file" case: CLI runs, `models.json` is created, exit code 0.
  - [x] Test graceful error handling for a failing provider.
- [x] **Commit "feat: registry CLI"**

---

## M6 – Integration Tests
- [x] **Task 19: Create integration test (`tests/integration/test_integration.py`)**
  - [x] Patch or mock provider `fetch_models()` methods (e.g., using `pytest-httpserver` for OpenAI if not overly complex, or simple monkeypatching for both) to return deterministic, distinct datasets for each provider.
  - [x] Run the `main` function from `src.model_registry.main` (or use `subprocess.run` to call `python -m model_registry.main`) in a temporary directory context where `models.json` will be written.
  - [x] Assert that `models.json` is created and its content matches the exact expected JSON structure and data (considering combined and sorted output from mocked providers).
  - [x] Assert that a second run of the `main` function results in "No changes" (e.g., by checking stdout or by ensuring the file's mtime doesn't change if content was identical).
- [X] **Commit "test: integration pipeline"**

---

## M7 – GitHub Action Automation
- [ ] **Task 20: Add GitHub Action workflow (`.github/workflows/refresh_model_registry.yml`)**
  - [ ] Workflow name: e.g., "Refresh model registry".
  - [ ] Triggers:
    - `schedule`: cron `*/30 * * * *` (every 30 minutes).
    - `workflow_dispatch`: for manual runs.
  - [ ] Job `update`:
    - `runs-on: ubuntu-latest`.
    - Steps:
      - `actions/checkout@v4` (with `persist-credentials: true`).
      - `actions/setup-python@v5` (with `python-version: '3.11'`).
      - Install `uv`: `pip install uv`.
      - Install project dependencies: `uv pip install .`
      - Run updater script: `python -m model_registry.main`
        - `env`: Pass `OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}` and `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}`
      - Commit & push if changed:
        - Script to check `git diff --quiet models.json`.
        - If diff exists: configure git user/email, `git add models.json`, `git commit -m "chore: update models.json (YYYY-MM-DDTHH:MM:SSZ)"`, `git push`.
          (Consider adding `if: github.repository == 'YOUR_ORG/YOUR_REPO'` to the push step if this will be forked).
        - If no diff: echo "No changes – skipping commit."
- [ ] **Task 21: Test GitHub Action workflow**
  - [ ] Create a test branch.
  - [ ] Add dummy secrets to the repository settings for the test branch (if necessary and safe) or use a fork.
  - [ ] Trigger the workflow manually (`workflow_dispatch`) or by pushing to the test branch.
  - [ ] Verify it runs, installs dependencies, executes the script, and correctly commits/pushes only if `models.json` changes.
- [ ] **Commit "ci: automated refresh action"**

---

## M8 – Anthropic Provider
- [ ] **Task 14: Add `anthropic` SDK dependency**
  - [ ] Add `anthropic` to `pyproject.toml` dependencies.
  - [ ] Run `uv pip install anthropic`.
- [ ] **Task 15: Implement `src/model_registry/providers/anthropic.py`**
  - [ ] Define `AnthropicProvider(Provider)` with `slug = "anthropic"`.
  - [ ] `fetch_models()`:
    - Use `anthropic.Anthropic().models.list()` (ensure API key is loaded from `ANTHROPIC_API_KEY` env var by the SDK).
    - Apply retry decorator.
  - [ ] `filter_public()`: Return raw input (passthrough, as current SDK call returns public models).
  - [ ] `get_developer()`: Return `"anthropic"`.
  - [ ] `get_release_date()`: Parse ISO date string from `model_record["created_at"]` (or equivalent field from SDK response) to `datetime.date`.
- [ ] **Task 16: Unit tests for `anthropic.py` (in `tests/unit/test_anthropic.py`)**
  - [ ] Monkeypatch `anthropic.Anthropic().models.list` to return mock model data.
  - [ ] Test `fetch_models()`.
  - [ ] Test `get_release_date()` parsing.
  - [ ] Test `normalize()` and `public_models()`.
- [ ] **Commit "feat: Anthropic provider"**

---

## M9 – Documentation & Dev UX
- [ ] **Task 22: Update documentation and provide developer setup files**
  - [ ] Expand `README.md`:
    - Project overview/purpose.
    - Example of `models.json` structure.
    - Snippet of `ModelEntry` Pydantic schema.
    - Quick-start guide:
      - Cloning the repo.
      - Setting up Python 3.11.
      - Installing `uv`.
      - Installing dependencies (`uv pip install -e .[dev]`).
      - Copying `.env.example` (if not already created in M1) to `.env` and adding API keys.
      - Running the registry update locally (`python -m model_registry.main`).
      - Running tests (`pytest`).
    - Guide on how to add a new provider (subclass `Provider`, implement methods, add to `PROVIDERS` list in `main.py`).
    - Brief overview of provider architecture.
    - Add note about GitHub Action fork behavior/guard if implemented.
  - [ ] Create `.env.example` file: (This task is moved to M1, ensure this is just a doc reference if M1 task exists)
    - `OPENAI_API_KEY=""`
    - `ANTHROPIC_API_KEY=""`
- [ ] **Commit "docs: initial documentation"**

---

## Final QA & Release
- [ ] **Task 23: Add linting/typing tools, run checks, and perform final code review**
  - [ ] Add `ruff` and `mypy` to `pyproject.toml` (e.g., in a `[project.optional-dependencies]` group like `dev`).
  - [ ] Configure `ruff` and `mypy` (e.g., in `pyproject.toml`).
  - [ ] Run `ruff format .` and `ruff check --fix .` to format and lint; resolve any reported issues.
  - [ ] Run `mypy src tests --strict` (or chosen strictness level); resolve any type errors.
  - [ ] Perform a final manual code review of all components.
- [ ] **Run full `pytest` suite — ensure all tests are green.**
- [ ] **Tag `v0.1.0` release on GitHub.**
  - [ ] Ensure `pyproject.toml` version is `0.1.0`.
  - [ ] `git tag v0.1.0`
  - [ ] `git push origin v0.1.0`

---

### Nice-to-Have (post-MVP)
- [ ] Provider-agnostic caching layer.
- [ ] Support additional providers (Google, TogetherAI, Fireworks).
- [ ] Publish GitHub Pages site rendering `models.json`.
- [ ] Add a simple FastAPI endpoint to serve `models.json`.

---
