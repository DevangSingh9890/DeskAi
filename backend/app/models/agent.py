from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.chat import ChatRequest
from app.models.ticket import SimilarTicket, TicketRecommendation, TicketStatusResponse


class RefinementHistoryMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str
    satisfaction: Literal["helpful", "not_helpful"] | None = None


class AgentRefinementContext(BaseModel):
    original_question: str = Field(min_length=1)
    previous_response: str = Field(min_length=1)
    conversation_history: list[RefinementHistoryMessage] = Field(
        default_factory=list,
        max_length=10,
    )
    classification: dict[str, Any] = Field(default_factory=dict)
    troubleshooting: dict[str, Any] = Field(default_factory=dict)
    knowledge_sources: list[str] = Field(default_factory=list)
    knowledge_results: list[dict[str, Any]] = Field(default_factory=list)
    ticket_recommendation: TicketRecommendation | None = None
    similar_tickets: list[SimilarTicket] = Field(default_factory=list)
    ticket_status: TicketStatusResponse | None = None


class AgentChatRequest(ChatRequest):
    refinement_context: AgentRefinementContext | None = None


class AgentChatResponse(BaseModel):
    classification: dict[str, Any]
    knowledge_sources: list[str]
    knowledge_results: list[dict[str, Any]] = Field(default_factory=list)
    troubleshooting: dict[str, Any]
    response: str
    ticket_recommendation: TicketRecommendation | None = None
    similar_tickets: list[SimilarTicket] = Field(default_factory=list)
    ticket_status: TicketStatusResponse | None = None
