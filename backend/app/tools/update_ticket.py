from typing import Any

from langchain_core.tools import tool

from app.models.ticket import TicketUpdateRequest
from app.services.ticket_service import ticket_service


@tool("update_ticket")
def update_ticket_tool(ticket_id: str, updates: dict[str, Any]) -> dict[str, object]:
    """Update allowed fields on an existing service desk ticket."""
    request = TicketUpdateRequest.model_validate(updates)
    ticket = ticket_service.update_ticket(ticket_id, request)
    return ticket.model_dump(mode="json")
