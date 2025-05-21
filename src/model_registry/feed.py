from pathlib import Path
from typing import List
from feedgen.feed import FeedGenerator
from feedgen.ext.base import BaseExtension, BaseEntryExtension
from lxml import etree # Required for creating custom elements
from .schemas import ModelEntry

# Define a namespace for your custom elements
MODEL_REGISTRY_NS = "http://example.com/model-registry/ns" # Replace with your actual namespace URL


def build_atom_feed(new_models: List[ModelEntry], repo_url: str, output_path: Path) -> None:
    """
    Generates an Atom feed from a list of new model entries and saves it to a file.

    Args:
        new_models: A list of ModelEntry objects representing newly added models.
        repo_url: The URL of the repository, used for generating feed and entry IDs.
        output_path: The path where the generated Atom feed (feed.xml) will be saved.
    """
    fg = FeedGenerator()
    fg.id(f"{repo_url}/feed.xml")
    fg.title("Model Registry Updates")
    fg.link(href=repo_url, rel="alternate")
    fg.subtitle("Updates to the public LLM model registry")
    fg.language("en")

    # Sort models by release date (newest first), then by model_id (alphabetically)
    sorted_models = sorted(new_models, key=lambda m: (-m.release_date.toordinal(), m.model_id))

    for model in sorted_models:
        entry = fg.add_entry()
        entry.id(f"urn:model-registry:{model.provider}:{model.developer}:{model.model_id}")
        entry.title(f"{model.provider} - {model.developer} - {model.model_id}")

        # --- dedicated Atom fields (no custom extension needed) ---
        entry.published(model.release_date.isoformat() + "T00:00:00Z")
        entry.category(term=model.provider, label="provider")
        entry.category(term=model.developer, label="developer")
        entry.category(term=model.model_id, label="model_id")
        entry.category(term=model.release_date.isoformat(), label="release_date")
        entry.category(term=model.status, label="status")

        # Human-readable HTML body (unchanged)
        content = (
            f"Provider: {model.provider}<br/>"
            f"Model ID: {model.model_id}<br/>"
            f"Release Date: {model.release_date.isoformat()}<br/>"
            f"Developer: {model.developer}<br/>"
            f"Status: {model.status}"
        )
        entry.content(content, type="html")

    feed_file_path = output_path / "feed.xml"
    fg.atom_file(str(feed_file_path), pretty=True) # Added pretty=True for readability
    print(f"Atom feed generated at {feed_file_path}") 