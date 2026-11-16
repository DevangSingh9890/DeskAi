from typing import Any

from pydantic import BaseModel


class AgentChatResponse(BaseModel):
    classification: dict[str, Any]
    knowledge_sources: list[str]
    troubleshooting: dict[str, Any]
    response: str
