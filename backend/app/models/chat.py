from pydantic import BaseModel, ConfigDict, Field

from app.models.classification import IncidentClassification


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, description="Message to send to the AI assistant")


class ChatResponse(BaseModel):
    response: str
    classification: IncidentClassification
