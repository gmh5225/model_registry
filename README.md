# Model Registry

A public registry of LLM models from various providers. 

## Running the Registry Update

To update the `models.json` file with the latest models from the configured providers, you can run the main script from the root of the project. This script will fetch model data, compare it to the existing `models.json`, and update the file if there are any changes.

Execute the following command in your terminal:

```bash
python -m model_registry.main
``` 