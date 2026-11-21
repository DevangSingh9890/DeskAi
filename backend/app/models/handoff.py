from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HandoffTranscriptMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoffRequest(BaseModel):
    messages: list[HandoffTranscriptMessage] = Field(min_length=1, max_length=500)
    context: dict[str, Any] = Field(default_factory=dict)
    ticket_id: str | None = Field(default=None, max_length=32)
    priority: str = Field(default="Medium", max_length=20)
    category: str = Field(default="Unclassified", max_length=100)


class HandoffAcceptRequest(BaseModel):
    agent_name: str = Field(default="Support Engineer", min_length=1, max_length=150)


class HandoffSendMessageRequest(BaseModel):
    sender_type: Literal["user", "agent"]
    message: str = Field(min_length=1, max_length=4000)


class HandoffMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    sender_type: Literal["user", "agent", "system"]
    message: str
    created_at: datetime


class HandoffConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    ticket_id: str | None
    status: str
    priority: str
    category: str
    assigned_agent: str | None
    context: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class HandoffQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    ticket_id: str | None
    status: str
    priority: str
    category: str
    assigned_agent: str | None
    created_at: datetime
    updated_at: datetime


class HandoffConversationDetail(BaseModel):
    conversation: HandoffConversationResponse
    messages: list[HandoffMessageResponse]
