from typing import Literal

from langchain_core.tools import tool

from app.models.ticket import TicketCreateRequest
from app.services.ticket_service import ticket_service

TicketPriority = Literal["Critical", "High", "Medium", "Low"]


@tool("create_ticket")
def create_ticket_tool(
    approval_id: str | None = None,
    message: str | None = None,
    title: str | None = None,
    description: str | None = None,
    priority: TicketPriority | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    assigned_group: str | None = None,
    created_by: str = "user",
) -> dict[str, object]:
    """Create a ticket from a matching human-approved recommendation or explicit ticket data."""
    if approval_id is not None or (message is not None and title is None):
        if message is None:
            raise ValueError("The original message is required for approval.")
        ticket = ticket_service.approve_ticket(approval_id, message)
    else:
        required = (
            title,
            description,
            priority,
            category,
            subcategory,
            assigned_group,
        )
        if any(value is None for value in required):
            raise ValueError("Complete ticket details are required.")
        request = TicketCreateRequest(
            title=title,
            description=description,
            priority=priority,
            category=category,
            subcategory=subcategory,
            assigned_group=assigned_group,
            created_by=created_by,
        )
        ticket = ticket_service.create_ticket(request)
    return ticket.model_dump(mode="json")
