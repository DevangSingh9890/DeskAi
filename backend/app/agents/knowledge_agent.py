import logging
from typing import Any

from app.graphs.state import ServiceDeskState
from app.services.rag_service import search_knowledge

logger = logging.getLogger(__name__)


def knowledge_agent(state: ServiceDeskState) -> dict[str, Any]:
    logger.info("Knowledge Agent Started")
    if not state.get("run_knowledge_search", True):
        return {"knowledge": {"chunks": [], "sources": []}}

    chunks = search_knowledge(state["user_message"], top_k=4)
    sources = list(
        dict.fromkeys(
            filename
            for chunk in chunks
            if isinstance((filename := chunk["metadata"].get("filename")), str)
            and filename
        )
    )
    return {"knowledge": {"chunks": chunks, "sources": sources}}
