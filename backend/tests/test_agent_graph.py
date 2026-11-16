import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.classification import IncidentClassification
from app.graphs.service_desk_graph import run_service_desk_graph


class ServiceDeskGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.classification = IncidentClassification(
            issue="VPN connection failure",
            category="Network",
            subcategory="VPN",
            priority="High",
            impact="Single User",
            assigned_group="Network Support",
            confidence_score=0.95,
        )

    def test_agent_chat_runs_graph_and_returns_sources_and_troubleshooting(self) -> None:
        with (
            patch(
                "app.agents.supervisor_agent.generate_json_response",
                return_value=(
                    '{"run_classification": true, "run_knowledge_search": true, '
                    '"run_troubleshooting": true}'
                ),
            ) as supervisor,
            patch(
                "app.agents.classification_agent.classify_incident_message",
                return_value=self.classification,
            ) as classifier,
            patch(
                "app.agents.knowledge_agent.search_knowledge",
                return_value=[
                    {
                        "content": "Restart the VPN client.",
                        "metadata": {"filename": "VPN Guide.pdf"},
                        "score": 0.91,
                    }
                ],
            ) as search,
            patch(
                "app.agents.troubleshooting_agent.generate_json_response",
                return_value=(
                    '{"likely_cause": "The VPN client is disconnected.", '
                    '"troubleshooting_steps": ["Restart the VPN client."], '
                    '"escalation_recommendation": "Contact Network Support '
                    'if the issue continues."}'
                ),
            ) as troubleshooter,
            self.assertLogs("app.graphs.service_desk_graph", level="INFO") as logs,
        ):
            response = self.client.post(
                "/api/agent/chat",
                json={"message": "My VPN is not connecting"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["classification"]["category"], "Network")
        self.assertEqual(body["classification"]["confidence"], 0.95)
        self.assertEqual(body["knowledge_sources"], ["VPN Guide.pdf"])
        self.assertEqual(
            body["troubleshooting"],
            {
                "likely_cause": "The VPN client is disconnected.",
                "troubleshooting_steps": ["Restart the VPN client."],
                "escalation_recommendation": (
                    "Contact Network Support if the issue continues."
                ),
            },
        )
        self.assertIn("Sources: VPN Guide.pdf", body["response"])
        supervisor.assert_called_once()
        classifier.assert_called_once_with("My VPN is not connecting")
        search.assert_called_once_with("My VPN is not connecting", top_k=4)
        troubleshooter.assert_called_once()
        self.assertIn("Graph Completed", "\n".join(logs.output))

    def test_supervisor_decisions_skip_unneeded_agents(self) -> None:
        with (
            patch(
                "app.agents.supervisor_agent.generate_json_response",
                return_value=(
                    '{"run_classification": false, '
                    '"run_knowledge_search": false, '
                    '"run_troubleshooting": false}'
                ),
            ),
            patch(
                "app.agents.classification_agent.classify_incident_message"
            ) as classifier,
            patch("app.agents.knowledge_agent.search_knowledge") as search,
            patch(
                "app.agents.troubleshooting_agent.generate_json_response"
            ) as troubleshooter,
        ):
            result = run_service_desk_graph("Hello")

        classifier.assert_not_called()
        search.assert_not_called()
        troubleshooter.assert_not_called()
        self.assertEqual(result["classification"], {})
        self.assertEqual(result["knowledge"], {"chunks": [], "sources": []})
        self.assertEqual(result["troubleshooting"], {})
        self.assertEqual(
            result["final_response"]["response"],
            "No troubleshooting action was required for this request.",
        )


if __name__ == "__main__":
    unittest.main()
