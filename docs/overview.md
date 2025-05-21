**Comprehensive Specification — "Public LLM Model Registry"**

---

## 1 · Project Goal

Create an automated, low-maintenance system that **fetches the public model catalog from multiple AI providers**, normalizes the data, and **writes a single JSON file (`models.json`) at the repo root**.
A GitHub Action runs every 30 minutes; it commits only when the JSON's *model content* changes (ignoring timestamp-only edits).

---

## 2 · High-Level Architecture

```
Model_Tracker/
│  models.json              ← generated, committed only on change
│  pyproject.toml           ← uv-compatible; declares deps & scripts
│  .env.example             ← sample vars for local dev
├─ src/
│   └─ model_registry/
│        __init__.py
│        main.py            ← CLI / entrypoint
│        schemas.py         ← Pydantic data models
│        providers/
│            base.py        ← abstract Provider class
│            openai.py
│            anthropic.py
│            # future_provider.py …
└─ tests/                   ← pytest unit/integration tests
```

---

## 3 · Data Contract

### 3.1 `models.json` format

```json
[
  {
    "provider": "openai",
    "model_id": "gpt-4o-mini-2024-07-18",
    "release_date": "2024-07-18",
    "developer": "openai"
  },
  {
    "provider": "anthropic",
    "model_id": "claude-3-7-sonnet-20250219",
    "release_date": "2025-02-19",
    "developer": "anthropic"
  }
  // ... more models
]
```

### 3.2 Pydantic schema (`schemas.py`)

```python
from datetime import date
from pydantic import BaseModel, Field

class ModelEntry(BaseModel):
    provider: str = Field(..., description="Provider slug, e.g., 'openai', 'anthropic'")
    id: str = Field(..., description="Provider's model ID / slug")
    release_date: date = Field(..., description="ISO YYYY-MM-DD")
    developer: str = Field(..., description="Original model creator")
```

---

## 4 · Provider Interface

### 4.1 Abstract class (`providers/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any
from .schemas import ModelEntry

class Provider(ABC):
    slug: str  # e.g. "openai"

    @abstractmethod
    def fetch_models(self) -> Iterable[Dict[str, Any]]:
        """Raw API call → iterable of provider records"""

    @abstractmethod
    def filter_public(self, raw: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        """Return only publicly-available models"""

    @abstractmethod
    def get_developer(self, model_record: Dict[str, Any]) -> str:
        """Return original creator (hard-coded logic allowed)"""

    @abstractmethod
    def get_release_date(self, model_record: Dict[str, Any]) -> date:
        """Return release date; fall back to today() if unknown"""

    def normalize(self, model_record: Dict[str, Any]) -> ModelEntry:
        return ModelEntry(
            provider=self.slug,
            model_id=model_record["id"],
            release_date=self.get_release_date(model_record),
            developer=self.get_developer(model_record),
        )

    def public_models(self) -> list[ModelEntry]:
        return [self.normalize(m) for m in self.filter_public(self.fetch_models())]
```

### 4.2 Concrete providers

* **OpenAI (`openai.py`)**

  * `fetch_models` → `GET /v1/models` via `requests`.
  * `filter_public` → keep where `"owned_by" == "openai"` and `":ft:"` **not** in `id`.
  * Other functions contain provider-specific heuristics you will fill in.

* **Anthropic (`anthropic.py`)**

  * Uses official Python SDK (`anthropic`).
  * Current `models.list()` already public; filter may simply return inputs.

* **Adding a provider**: create `<provider>.py` subclass, import in `main.py`, and add to `PROVIDERS` list.

---

## 5 · `main.py` Workflow (CLI & Action entry)

1. Load environment (`python-dotenv`) for local runs.
2. Iterate through `PROVIDERS` → build `registry: dict[str, list[ModelEntry]]`.
3. Serialize to JSON (indent=2) as text.
4. Compare with existing `models.json` (if any).

   * If **identical**, exit `0` (no commit).
   * If **different**, overwrite file and exit `0`; Action will commit.

---

## 6 · GitHub Action (`.github/workflows/update.yml`)

```yaml
name: Refresh model registry
on:
  schedule:
    - cron:  '*/30 * * * *'   # every 30 min
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: persist-credentials: true
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install uv
        run: |
          pip install uv
      - name: Install deps
        run: |
          uv pip install -q .
      - name: Run updater
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python -m model_registry.main
      - name: Commit & push if changed
        run: |
          if git diff --quiet; then
            echo "No changes – skipping commit."
          else
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add models.json
            git commit -m "chore: update models $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
            git push
          fi
```

*Relies on Git CLI; keeps history clean by committing only when file diff is non-empty.*

---

## 7 · Dependencies (declared in `pyproject.toml`)

| Purpose                         | Package                 |
| ------------------------------- | ----------------------- |
| HTTP requests (OpenAI)          | `requests`              |
| Anthropic SDK                   | `anthropic`             |
| Data validation                 | `pydantic`              |
| Env var loading (local)         | `python-dotenv`         |
| Testing                         | `pytest`, `pytest-mock` |
| Lint / type checking (optional) | `ruff`, `mypy`          |

`uv` resolves/install these during the Action.

---

## 8 · Error Handling Strategy

| Failure               | Behavior                                                                       | Notes                                |
| --------------------- | ------------------------------------------------------------------------------ | ------------------------------------ |
| Network/5xx           | Retry (exponential back-off, 3 attempts) then log & skip provider for this run | Prevents Action failure storms       |
| 401/403 (bad creds)   | Log clear message, exit non-zero                                               | Alerts maintainer via Action failure |
| Unexpected JSON shape | Catch, log, mark provider as errored; other providers continue                 | Isolates faults                      |
| Missing env vars      | Raise immediately with actionable message                                      | Fail fast                            |

---

## 9 · Testing Plan

1. **Unit tests** (`tests/unit/`)

   * Mock each provider's API response; assert `public_models()` returns correct `ModelEntry` list.
   * Verify filtering rules (e.g., OpenAI fine-tune exclusion).
2. **Normalization tests**

   * Given edge-case inputs (missing dates, unknown developers) ensure defaults/fallbacks work.
3. **Integration test** (`tests/integration/`)

   * Spin up script with `.env` and mocked HTTP endpoints (via `pytest-httpserver`) to confirm end-to-end JSON generation.
   * Simulate "no diff" vs "diff" situations; assert exit codes.
4. **Static checks**

   * `mypy --strict`, `ruff check` in CI.

---

## 10 · Extensibility Guidelines

* **Add provider** → create subclass, add to import list.
* **Add model fields** → extend `ModelEntry` and update `normalize`.
* **Change filtering** → adjust `filter_public` per provider without touching shared logic.
* **Alternate output formats** → write an extra serializer in `main.py` (e.g., CSV) but keep JSON canonical.

---

## 11 · Local Development

```bash
uv pip install -r pyproject.toml
cp .env.example .env       # add your keys
python -m model_registry.main   # prints diff / updates file
pytest -q
```

---

### Ready for implementation

All core requirements, directory layout, data contracts, update cadence, error-handling, and testing strategy are specified. A developer can scaffold the repo, populate the provider subclasses, and wire up the Action exactly as described.
