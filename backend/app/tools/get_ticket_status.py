from langchain_core.tools import tool

from app.services.ticket_service import ticket_service


@tool("get_ticket_status")
def get_ticket_status_tool(ticket_id: str) -> dict[str, object]:
    """Retrieve the current status and support group for a ticket."""
    result = ticket_service.get_ticket_status(ticket_id)
    return result.model_dump(mode="json")
