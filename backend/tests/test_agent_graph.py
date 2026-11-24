import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.agents.troubleshooting_agent import TroubleshootingResult
from app.models.classification import IncidentClassification
from app.services.groq_service import GroqTimeoutError
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
                    '"troubleshooting_steps": ["Restart the VPN client."]}'
                ),
            ) as troubleshooter,
            patch(
                "app.agents.ticket_agent.generate_json_response",
                return_value=(
                    '{"action": "no_action", '
                    '"reason": "No ticket action was requested."}'
                ),
            ) as ticket_agent,
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
                    "Contact the service desk if these steps do not resolve "
                    "the issue."
                ),
            },
        )
        self.assertIn("Sources: VPN Guide.pdf", body["response"])
        supervisor.assert_called_once()
        classifier.assert_called_once_with("My VPN is not connecting")
        search.assert_called_once_with("My VPN is not connecting", top_k=4)
        troubleshooter.assert_called_once()
        ticket_agent.assert_called_once()
        self.assertIn("Graph Completed", "\n".join(logs.output))

    def test_refinement_reuses_context_without_running_agent_graph_or_rag(self) -> None:
        refinement_context = {
            "original_question": "Help me reset my password.",
            "previous_response": "Use the password reset page.",
            "conversation_history": [
                {"role": "user", "content": "Help me reset my password."},
                {
                    "role": "assistant",
                    "content": "Use the password reset page.",
                    "satisfaction": "not_helpful",
                },
            ],
            "classification": {
                "issue": "Password reset",
                "category": "Access Management",
                "subcategory": "Password Reset",
            },
            "troubleshooting": {"troubleshooting_steps": ["Open the reset page."]},
            "knowledge_sources": ["Password Guide.pdf"],
            "knowledge_results": [
                {
                    "content": "Select Forgot Password on the sign-in page.",
                    "metadata": {"filename": "Password Guide.pdf"},
                    "score": 0.9,
                }
            ],
            "ticket_recommendation": None,
            "similar_tickets": [],
        }

        with (
            patch(
                "app.routes.chat.generate_refined_response",
                return_value="Try the Forgot Password link on the sign-in page.",
            ) as refine,
            patch("app.routes.chat.run_service_desk_graph") as graph,
            patch("app.agents.knowledge_agent.search_knowledge") as search,
        ):
            response = self.client.post(
                "/api/agent/chat",
                json={
                    "message": "I still cannot reset my password.",
                    "refinement_context": refinement_context,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["response"],
            "Try the Forgot Password link on the sign-in page.",
        )
        self.assertEqual(
            body["knowledge_sources"],
            ["Password Guide.pdf"],
        )
        self.assertEqual(
            body["classification"]["category"],
            "Access Management",
        )
        refine.assert_called_once()
        self.assertEqual(
            refine.call_args.args[0],
            "I still cannot reset my password.",
        )
        graph.assert_not_called()
        search.assert_not_called()

    def test_refinement_timeout_returns_specific_gateway_timeout(self) -> None:
        with patch(
            "app.routes.chat.generate_refined_response",
            side_effect=GroqTimeoutError("Groq timed out"),
        ):
            response = self.client.post(
                "/api/agent/chat",
                json={
                    "message": "I still cannot reset my password.",
                    "refinement_context": {
                        "original_question": "Help me reset my password.",
                        "previous_response": "Use the reset page.",
                    },
                },
            )

        self.assertEqual(response.status_code, 504)
        self.assertIn("25-second request limit", response.json()["detail"])

    def test_explicit_ticket_request_returns_approval_recommendation(self) -> None:
        message = "My laptop won't turn on. Please create a support ticket."
        with (
            patch(
                "app.agents.supervisor_agent.generate_json_response",
                return_value=(
                    '{"run_classification": true, "run_knowledge_search": false, '
                    '"run_troubleshooting": true}'
                ),
            ),
            patch(
                "app.agents.classification_agent.classify_incident_message",
                return_value=self.classification,
            ),
            patch("app.agents.knowledge_agent.search_knowledge", return_value=[]),
            patch(
                "app.agents.troubleshooting_agent.generate_json_response",
                return_value=(
                    '{"likely_cause": "The laptop may have lost power.", '
                    '"troubleshooting_steps": ["Check the charger."]}'
                ),
            ),
            patch(
                "app.agents.ticket_agent.generate_json_response"
            ) as ticket_agent_llm,
            patch(
                "app.agents.ticket_agent.ticket_service.request_ticket_approval",
                return_value="approval-token",
            ) as request_approval,
            patch(
                "app.agents.ticket_agent.ticket_service.create_ticket"
            ) as create_ticket,
        ):
            response = self.client.post(
                "/api/agent/chat",
                json={"message": message},
            )

        self.assertEqual(response.status_code, 200)
        recommendation = response.json()["ticket_recommendation"]
        self.assertEqual(recommendation["action"], "create_ticket")
        self.assertTrue(recommendation["ticket_recommended"])
        self.assertTrue(recommendation["requires_approval"])
        self.assertEqual(recommendation["approval_id"], "approval-token")
        ticket_agent_llm.assert_not_called()
        request_approval.assert_called_once()
        create_ticket.assert_not_called()

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
            patch(
                "app.agents.ticket_agent.generate_json_response",
                return_value=(
                    '{"action": "no_action", '
                    '"reason": "No ticket action was requested."}'
                ),
            ) as ticket_agent,
        ):
            result = run_service_desk_graph("Hello")

        classifier.assert_not_called()
        search.assert_not_called()
        troubleshooter.assert_not_called()
        ticket_agent.assert_called_once()
        self.assertEqual(result["classification"], {})
        self.assertEqual(result["knowledge"], {"chunks": [], "sources": []})
        self.assertEqual(result["troubleshooting"], {})
        self.assertEqual(
            result["final_response"]["response"],
            "No troubleshooting action was required for this request.",
        )
        self.assertFalse(result["ticket_recommendation"]["ticket_recommended"])

    def test_graph_invoke_logs_and_reraises_node_exception(self) -> None:
        with (
            patch(
                "app.graphs.service_desk_graph.service_desk_graph.invoke",
                side_effect=RuntimeError("test graph failure"),
            ),
            self.assertLogs("app.graphs.service_desk_graph", level="ERROR") as logs,
        ):
            with self.assertRaisesRegex(RuntimeError, "test graph failure"):
                run_service_desk_graph("My VPN is not connecting")

        self.assertIn("LangGraph execution failed", "\n".join(logs.output))

    def test_graph_validation_errors_are_detailed_only_in_development(self) -> None:
        with self.assertRaises(ValidationError) as invalid_output:
            TroubleshootingResult.model_validate_json(
                '{"troubleshooting_steps": []}'
            )

        with (
            patch(
                "app.routes.chat.run_service_desk_graph",
                side_effect=invalid_output.exception,
            ),
            patch(
                "app.routes.chat.settings",
                SimpleNamespace(APP_ENV="development"),
            ),
            self.assertLogs("app.routes.chat", level="ERROR"),
        ):
            development_response = self.client.post(
                "/api/agent/chat",
                json={"message": "My VPN is not connecting"},
            )

        self.assertEqual(development_response.status_code, 502)
        self.assertIn("likely_cause", development_response.json()["detail"])

        with (
            patch(
                "app.routes.chat.run_service_desk_graph",
                side_effect=invalid_output.exception,
            ),
            patch(
                "app.routes.chat.settings",
                SimpleNamespace(APP_ENV="production"),
            ),
            self.assertLogs("app.routes.chat", level="ERROR"),
        ):
            production_response = self.client.post(
                "/api/agent/chat",
                json={"message": "My VPN is not connecting"},
            )

        self.assertEqual(production_response.status_code, 502)
        self.assertEqual(
            production_response.json()["detail"],
            "The service-desk agent workflow failed.",
        )


if __name__ == "__main__":
    unittest.main()
