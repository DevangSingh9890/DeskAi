from langchain_core.tools import tool

from app.services.ticket_service import ticket_service


@tool("assign_ticket")
def assign_ticket_tool(ticket_id: str, assigned_group: str) -> dict[str, object]:
    """Assign a ticket to a support group."""
    ticket = ticket_service.assign_ticket(ticket_id, assigned_group)
    return ticket.model_dump(mode="json")
