from typing import Any

from pydantic import BaseModel, Field

from app.models.ticket import SimilarTicket, TicketRecommendation, TicketStatusResponse


class AgentChatResponse(BaseModel):
    classification: dict[str, Any]
    knowledge_sources: list[str]
    knowledge_results: list[dict[str, Any]] = Field(default_factory=list)
    troubleshooting: dict[str, Any]
    response: str
    ticket_recommendation: TicketRecommendation | None = None
    similar_tickets: list[SimilarTicket] = Field(default_factory=list)
    ticket_status: TicketStatusResponse | None = None
