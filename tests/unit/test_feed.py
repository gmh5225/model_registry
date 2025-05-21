import pytest
from pathlib import Path
from datetime import date, datetime
from typing import List
from xml.etree import ElementTree as ET # For parsing XML

from model_registry.schemas import ModelEntry
from model_registry.feed import build_atom_feed

@pytest.fixture
def sample_models() -> List[ModelEntry]:
    return [
        ModelEntry(
            provider="test_provider_1",
            model_id="model_alpha",
            release_date=date(2023, 1, 15),
            developer="dev_a",
            status="active",
        ),
        ModelEntry(
            provider="test_provider_2",
            model_id="model_beta_20230320", # Model ID with date hint
            release_date=date(2023, 3, 20),
            developer="dev_b",
            status="active",
        ),
        ModelEntry(
            provider="test_provider_1",
            model_id="model_gamma_older",
            release_date=date(2022, 12, 1),
            developer="dev_a",
            status="deprecated",
        ),
    ]

@pytest.fixture
def repo_url() -> str:
    return "https://example.com/test-repo"


def test_build_atom_feed_creates_valid_file(tmp_path: Path, sample_models: List[ModelEntry], repo_url: str):
    """Test that build_atom_feed creates a well-formed Atom XML file with correct entries."""
    output_dir = tmp_path / "feed_output"
    output_dir.mkdir()

    build_atom_feed(sample_models, repo_url, output_dir)

    feed_file = output_dir / "feed.xml"
    assert feed_file.exists(), "feed.xml was not created"
    assert feed_file.is_file()

    try:
        tree = ET.parse(str(feed_file))
        root = tree.getroot()
    except ET.ParseError as e:
        pytest.fail(f"Generated feed.xml is not well-formed XML: {e}")

    # Atom namespace - typically Atom 1.0
    ns = {'atom': 'http://www.w3.org/2005/Atom'}

    # Basic feed metadata checks
    assert root.tag == f"{{{ns['atom']}}}feed", "Root element is not <feed>"
    assert root.find('atom:title', ns).text == "Model Registry Updates"
    assert root.find('atom:id', ns).text == f"{repo_url}/feed.xml"
    assert root.find('atom:link[@rel="alternate"]', ns).get('href') == repo_url

    entries = root.findall('atom:entry', ns)
    assert len(entries) == len(sample_models), "Number of entries does not match number of models"

    # Sort sample models as they would be in the feed (newest first)
    expected_sorted_models = sorted(sample_models, key=lambda m: (-m.release_date.toordinal(), m.model_id))
    
    # Create a map of entry IDs to models for verification
    entry_id_to_model = {f"{repo_url}/model/{model.provider}/{model.model_id}/{model.release_date.isoformat()}": model 
                        for model in expected_sorted_models}
    
    # Verify each entry matches a model based on its ID
    for entry_elem in entries:
        entry_id = entry_elem.find('atom:id', ns).text
        assert entry_id in entry_id_to_model, f"Entry ID {entry_id} not found in expected models"
        
        model = entry_id_to_model[entry_id]
        entry_title = entry_elem.find('atom:title', ns).text
        entry_updated_str = entry_elem.find('atom:updated', ns).text
        entry_link = entry_elem.find('atom:link', ns).get('href')
        entry_content = entry_elem.find('atom:content', ns).text
        
        assert entry_title == f"New Model: {model.provider} - {model.model_id}"
        assert entry_link == f"{repo_url}#model-{model.provider}-{model.model_id}"
        
        # Check updated timestamp matches model's release date
        expected_updated_dt = datetime.combine(model.release_date, datetime.min.time())
        # Allow for either Z or +00:00 format for UTC timezone
        assert entry_updated_str in [expected_updated_dt.isoformat() + "Z", 
                                   expected_updated_dt.isoformat() + "+00:00"]
        
        # Check content details
        assert f"Provider: {model.provider}" in entry_content
        assert f"Model ID: {model.model_id}" in entry_content
        assert f"Release Date: {model.release_date.isoformat()}" in entry_content
        assert f"Developer: {model.developer}" in entry_content
        assert f"Status: {model.status}" in entry_content


def test_build_atom_feed_empty_models_list(tmp_path: Path, repo_url: str):
    """Test that build_atom_feed handles an empty list of models gracefully (creates an empty feed)."""
    output_dir = tmp_path / "feed_output_empty"
    output_dir.mkdir()

    build_atom_feed([], repo_url, output_dir)

    feed_file = output_dir / "feed.xml"
    assert feed_file.exists(), "feed.xml was not created even for empty models list"

    tree = ET.parse(str(feed_file))
    root = tree.getroot()
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('atom:entry', ns)
    assert len(entries) == 0, "Feed should have no entries for an empty model list"
    assert root.find('atom:title', ns).text == "Model Registry Updates"

# TODO: Add integration test: run CLI twice and assert feed updates only when new models appear.
# This would go in tests/integration/test_integration.py or a similar file.
# It would involve:
# 1. Running main() once with a set of mock models, capturing models.json and feed.xml.
# 2. Running main() again with the *same* mock models, asserting feed.xml is *not* regenerated or is identical.
# 3. Running main() with *new* mock models added, asserting feed.xml *is* updated with only the new entries. 