import unittest
from unittest.mock import Mock, patch

from app.agents.ticket_agent import ticket_agent
from app.models.ticket import TicketStatusResponse


class TicketAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = {
            "user_message": "My VPN is not connecting before a meeting.",
            "classification": {
                "issue": "VPN connection failure",
                "category": "Network",
                "subcategory": "VPN",
                "priority": "High",
                "assigned_group": "Network Support",
                "confidence_score": 0.95,
            },
            "knowledge": {"chunks": [], "sources": []},
            "troubleshooting": {
                "likely_cause": "The VPN client is disconnected.",
                "troubleshooting_steps": ["Reconnect VPN."],
                "escalation_recommendation": "Escalate if reconnecting fails.",
            },
        }

    def test_create_decision_requests_approval_without_creating_ticket(self) -> None:
        with (
            patch(
                "app.agents.ticket_agent.generate_json_response",
                return_value=(
                    '{"action": "create_ticket", '
                    '"reason": "The work-blocking incident should be tracked."}'
                ),
            ),
            patch(
                "app.agents.ticket_agent.ticket_service.request_ticket_approval",
                return_value="approval-token",
            ) as request_approval,
            patch(
                "app.agents.ticket_agent.ticket_service.create_ticket"
            ) as create_ticket,
        ):
            result = ticket_agent(self.state)

        request_approval.assert_called_once_with(
            self.state["user_message"],
            self.state["classification"],
        )
        create_ticket.assert_not_called()
        self.assertEqual(
            result["ticket_recommendation"],
            {
                "action": "create_ticket",
                "ticket_recommended": True,
                "reason": "The work-blocking incident should be tracked.",
                "requires_approval": True,
                "approval_id": "approval-token",
            },
        )

    def test_explicit_ticket_request_bypasses_llm_and_requests_approval(self) -> None:
        self.state["user_message"] = (
            "My laptop won't turn on. Please create a support ticket."
        )
        with (
            patch(
                "app.agents.ticket_agent.generate_json_response",
                side_effect=ValueError("LLM returned invalid action data"),
            ) as generate,
            patch(
                "app.agents.ticket_agent.ticket_service.request_ticket_approval",
                return_value="approval-token",
            ) as request_approval,
            patch(
                "app.agents.ticket_agent.ticket_service.create_ticket"
            ) as create_ticket,
        ):
            result = ticket_agent(self.state)

        generate.assert_not_called()
        request_approval.assert_called_once_with(
            self.state["user_message"],
            self.state["classification"],
        )
        create_ticket.assert_not_called()
        self.assertTrue(result["ticket_recommendation"]["ticket_recommended"])
        self.assertTrue(result["ticket_recommendation"]["requires_approval"])
        self.assertEqual(
            result["ticket_recommendation"]["approval_id"],
            "approval-token",
        )

    def test_explicit_ticket_request_reports_missing_classification(self) -> None:
        self.state["user_message"] = "Please raise an incident ticket."
        self.state["classification"] = {"issue": "Laptop failure"}
        with (
            patch(
                "app.agents.ticket_agent.generate_json_response"
            ) as generate,
            patch(
                "app.agents.ticket_agent.ticket_service.request_ticket_approval"
            ) as request_approval,
        ):
            result = ticket_agent(self.state)

        generate.assert_not_called()
        request_approval.assert_not_called()
        recommendation = result["ticket_recommendation"]
        self.assertEqual(recommendation["action"], "create_ticket")
        self.assertFalse(recommendation["ticket_recommended"])
        self.assertIn("classification is missing or invalid", recommendation["reason"])
        self.assertIn("priority", recommendation["reason"])

    def test_negated_ticket_request_keeps_llm_routing(self) -> None:
        self.state["user_message"] = "Please don't create a support ticket."
        with patch(
            "app.agents.ticket_agent.generate_json_response",
            return_value=(
                '{"action": "no_action", "reason": "The user declined a ticket."}'
            ),
        ) as generate:
            result = ticket_agent(self.state)

        generate.assert_called_once()
        self.assertFalse(result["ticket_recommendation"]["ticket_recommended"])

    def test_status_decision_uses_status_tool(self) -> None:
        self.state["user_message"] = "What is the status of INC-10001?"
        with (
            patch(
                "app.agents.ticket_agent.generate_json_response",
                return_value=(
                    '{"action": "check_ticket_status", '
                    '"reason": "The user asked for the current status.", '
                    '"ticket_id": "INC-10001"}'
                ),
            ),
            patch(
                "app.agents.ticket_agent.get_ticket_status_tool",
                new=Mock(
                    invoke=Mock(
                        return_value={
                            "ticket_id": "INC-10001",
                            "status": "Open",
                            "assigned_group": "Network Support",
                            "updated_at": "2026-11-16T08:30:00+00:00",
                        }
                    )
                ),
            ) as get_status,
        ):
            result = ticket_agent(self.state)

        get_status.invoke.assert_called_once_with({"ticket_id": "INC-10001"})
        self.assertEqual(result["ticket_status"]["status"], "Open")
        self.assertFalse(
            result["ticket_recommendation"]["ticket_recommended"]
        )

    def test_similar_incident_decision_uses_search_tool(self) -> None:
        similar_ticket = {
            "ticket_id": "INC-10001",
            "category": "Network",
            "priority": "High",
            "summary": "VPN client could not connect",
            "resolution": "Reconnected the VPN client.",
        }
        with (
            patch(
                "app.agents.ticket_agent.generate_json_response",
                return_value=(
                    '{"action": "find_similar_incidents", '
                    '"reason": "A related historical resolution may help."}'
                ),
            ),
            patch(
                "app.agents.ticket_agent.search_similar_tickets_tool",
                new=Mock(invoke=Mock(return_value=[similar_ticket])),
            ) as search,
        ):
            result = ticket_agent(self.state)

        search.invoke.assert_called_once()
        self.assertEqual(result["similar_tickets"], [similar_ticket])
        self.assertFalse(
            result["ticket_recommendation"]["requires_approval"]
        )

    def test_status_model_accepts_missing_ticket_result(self) -> None:
        status = TicketStatusResponse(
            ticket_id="INC-99999",
            status="Not found",
            assigned_group=None,
            updated_at=None,
        )
        self.assertEqual(status.status, "Not found")

    def test_missing_ticket_status_returns_not_found_result(self) -> None:
        self.state["user_message"] = "What is the status of INC-99999?"
        with patch(
            "app.agents.ticket_agent.generate_json_response",
            return_value=(
                '{"action": "check_ticket_status", '
                '"reason": "The user asked for the current status.", '
                '"ticket_id": "INC-99999"}'
            ),
        ):
            result = ticket_agent(self.state)

        self.assertEqual(result["ticket_status"]["status"], "Not found")


if __name__ == "__main__":
    unittest.main()
