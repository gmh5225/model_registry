import pytest
from datetime import date
from pydantic import ValidationError
from model_registry.schemas import ModelEntry

def test_valid_model_entry():
    """Test that a valid ModelEntry instance passes validation."""
    data = {
        "provider": "openai",
        "model_id": "gpt-4",
        "release_date": "2023-03-14",
        "developer": "OpenAI",
        "status": "active"
    }
    entry = ModelEntry(**data)
    assert entry.provider == "openai"
    assert entry.model_id == "gpt-4"
    assert entry.release_date == date(2023, 3, 14)
    assert entry.developer == "OpenAI"
    assert entry.status == "active"

def test_model_entry_missing_required_fields():
    """Test that missing required fields raise pydantic.ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        ModelEntry(provider="openai", model_id="gpt-4")
    
    errors = excinfo.value.errors()
    error_locs = {err['loc'][0] for err in errors}
    assert "release_date" in error_locs
    assert "developer" in error_locs
    assert len(errors) == 2

def test_model_entry_empty_id():
    """Test that an empty id raises pydantic.ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        ModelEntry(
            provider="openai",
            model_id="",
            release_date="2023-01-01",
            developer="OpenAI"
        )
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]['loc'][0] == 'model_id'
    assert "String should have at least 1 character" in errors[0]['msg']


def test_model_entry_invalid_date_format():
    """Test that a non-ISO format string for release_date raises pydantic.ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        ModelEntry(
            provider="openai",
            model_id="gpt-3",
            release_date="01/02/2023", # Invalid format DD/MM/YYYY
            developer="OpenAI"
        )
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]['loc'][0] == 'release_date'
    assert "input should be a valid date" in errors[0]['msg'].lower()

    with pytest.raises(ValidationError) as excinfo_text:
        ModelEntry(
            provider="openai",
            model_id="gpt-3.5",
            release_date="Mar 1st 2023", # Invalid format text
            developer="OpenAI"
        )
    errors_text = excinfo_text.value.errors()
    assert len(errors_text) == 1
    assert errors_text[0]['loc'][0] == 'release_date'
    assert "input should be a valid date" in errors_text[0]['msg'].lower()


def test_model_entry_status_default_and_valid_values():
    """Test status field defaults and accepts valid values."""
    # Test default value
    entry_default_status = ModelEntry(
        provider="openai",
        model_id="gpt-2",
        release_date="2019-02-14",
        developer="OpenAI"
    )
    assert entry_default_status.status == "active"

    # Test providing a valid status
    entry_deprecated_status = ModelEntry(
        provider="openai",
        model_id="gpt-1",
        release_date="2018-06-11",
        developer="OpenAI",
        status="deprecated"
    )
    assert entry_deprecated_status.status == "deprecated"

    # Pydantic by default doesn't restrict string fields to a specific set of values
    # unless an Enum or Literal is used. The current schema uses `str`.
    # If specific values like "active", "deprecated" are the ONLY allowed ones,
    # the schema should be updated (e.g., using `Literal["active", "deprecated"]`).
    # For now, this test just ensures it accepts a string.
    entry_custom_status = ModelEntry(
        provider="openai",
        model_id="text-davinci-003",
        release_date="2022-01-01", # Fictional date for example
        developer="OpenAI",
        status="experimental" # Another valid string
    )
    assert entry_custom_status.status == "experimental" 