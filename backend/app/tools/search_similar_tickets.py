from langchain_core.tools import tool

from app.services.ticket_service import ticket_service


@tool("search_similar_tickets")
def search_similar_tickets_tool(
    query: str,
    category: str | None = None,
    priority: str | None = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    """Search historical tickets for related incidents and resolutions."""
    results = ticket_service.search_similar_tickets(
        query,
        category=category,
        priority=priority,
        limit=limit,
    )
    return [result.model_dump(mode="json") for result in results]
