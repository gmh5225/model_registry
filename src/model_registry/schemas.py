from datetime import date
from pydantic import BaseModel, Field, constr

class ModelEntry(BaseModel):
    provider: str = Field(..., description="Provider slug, e.g., 'openai', 'anthropic', 'together'")
    developer: str = Field(..., description="Original model creator, e.g., 'meta', 'quora'")
    model_id: str = Field(..., min_length=1, description="Provider's model ID / slug")
    release_date: date = Field(..., description="ISO YYYY-MM-DD")
    status: str = Field("active", description="e.g., 'active', 'deprecated'") 