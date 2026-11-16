import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.classification_agent import classification_agent
from app.agents.knowledge_agent import knowledge_agent
from app.agents.supervisor_agent import supervisor_agent
from app.agents.troubleshooting_agent import troubleshooting_agent
from app.graphs.state import ServiceDeskState

logger = logging.getLogger(__name__)


def build_service_desk_graph() -> Any:
    graph = StateGraph(ServiceDeskState)
    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("classification", classification_agent)
    graph.add_node("knowledge", knowledge_agent)
    graph.add_node("troubleshooting", troubleshooting_agent)

    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "classification")
    graph.add_edge("classification", "knowledge")
    graph.add_edge("knowledge", "troubleshooting")
    graph.add_edge("troubleshooting", END)
    return graph.compile()


service_desk_graph = build_service_desk_graph()


def run_service_desk_graph(user_message: str) -> dict[str, Any]:
    result = service_desk_graph.invoke(
        {
            "user_message": user_message,
            "classification": {},
            "knowledge": {"chunks": [], "sources": []},
            "troubleshooting": {},
            "final_response": {},
        }
    )
    logger.info("Graph Completed")
    return result
