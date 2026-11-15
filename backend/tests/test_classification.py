import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.agents.classification_agent import (
    ClassificationAgentError,
    classify_incident_message,
)
from app.models.classification import IncidentClassification


class ClassificationAgentTests(unittest.TestCase):
    def test_agent_validates_structured_classification(self) -> None:
        with patch(
            "app.agents.classification_agent.generate_json_response",
            return_value=(
                '{"issue":"VPN connection failure","category":"Network",'
                '"subcategory":"VPN","priority":"High","impact":"Single User",'
                '"assigned_group":"Network Support","confidence_score":0.95}'
            ),
        ) as generate_mock:
            result = classify_incident_message("VPN will not connect.")

        self.assertIsInstance(result, IncidentClassification)
        self.assertEqual(result.category, "Network")
        self.assertEqual(result.priority, "High")
        self.assertEqual(result.confidence_score, 0.95)
        generate_mock.assert_called_once()

    def test_agent_rejects_invalid_category(self) -> None:
        with patch(
            "app.agents.classification_agent.generate_json_response",
            return_value=(
                '{"issue":"Issue","category":"Unknown","subcategory":"Other",'
                '"priority":"Low","impact":"Single User",'
                '"assigned_group":"Support","confidence_score":0.5}'
            ),
        ):
            with self.assertRaises(ClassificationAgentError):
                classify_incident_message("Issue")

    def test_confidence_score_must_be_between_zero_and_one(self) -> None:
        with self.assertRaises(ValidationError):
            IncidentClassification(
                issue="Issue",
                category="Network",
                subcategory="VPN",
                priority="Low",
                impact="Single User",
                assigned_group="Network Support",
                confidence_score=1.1,
            )


if __name__ == "__main__":
    unittest.main()
