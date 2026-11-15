import logging

from app.agents.classification_agent import (
    ClassificationAgentError,
    classify_incident_message,
)
from app.models.classification import IncidentClassification

logger = logging.getLogger(__name__)


class ClassificationServiceError(RuntimeError):
    pass


def classify_incident(message: str) -> IncidentClassification:
    try:
        return classify_incident_message(message)
    except ClassificationAgentError as exc:
        logger.error("Incident classification failed: %s", exc)
        raise ClassificationServiceError(
            "The incident could not be classified."
        ) from exc
