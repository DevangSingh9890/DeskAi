from typing import Any, TypedDict


class ServiceDeskState(TypedDict, total=False):
    user_message: str
    run_classification: bool
    run_knowledge_search: bool
    run_troubleshooting: bool
    classification: dict[str, Any]
    knowledge: dict[str, Any]
    troubleshooting: dict[str, Any]
    final_response: dict[str, Any]
