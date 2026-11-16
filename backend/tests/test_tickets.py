import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.models.ticket import (
    TicketCreateRequest,
    TicketUpdateRequest,
)
from app.services.ticket_service import (
    InMemoryTicketRepository,
    PendingApprovalNotFoundError,
    TicketService,
    ticket_service,
)


class TicketServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TicketService(InMemoryTicketRepository())
        self.message = "My VPN is not connecting"
        self.classification = {
            "issue": "VPN connection failure",
            "priority": "High",
            "category": "Network",
            "subcategory": "VPN",
            "assigned_group": "Network Support",
        }

    def test_ticket_is_created_only_after_matching_approval(self) -> None:
        approval_id = self.service.request_ticket_approval(
            self.message,
            self.classification,
        )

        self.assertEqual(self.service.list_tickets(), [])
        ticket = self.service.approve_ticket(approval_id, self.message)

        self.assertEqual(ticket.ticket_id, "INC-10001")
        self.assertEqual(ticket.status, "Open")
        self.assertEqual(ticket.assigned_group, "Network Support")
        with self.assertRaises(PendingApprovalNotFoundError):
            self.service.approve_ticket(approval_id, self.message)

    def test_stale_approval_id_recovers_by_exact_original_message(self) -> None:
        self.service.request_ticket_approval(self.message, self.classification)

        ticket = self.service.approve_ticket("stale-approval-id", self.message)

        self.assertEqual(ticket.title, "VPN connection failure")
        self.assertEqual(ticket.status, "Open")
        self.assertEqual(self.service.list_tickets(), [ticket])

    def test_rejected_recommendation_does_not_create_ticket(self) -> None:
        approval_id = self.service.request_ticket_approval(
            self.message,
            self.classification,
        )

        self.service.reject_ticket_approval(approval_id, self.message)

        self.assertEqual(self.service.list_tickets(), [])
        with self.assertRaises(PendingApprovalNotFoundError):
            self.service.approve_ticket(approval_id, self.message)

    def test_ticket_update_status_and_similar_search(self) -> None:
        ticket = self.service.create_ticket(
            TicketCreateRequest(
                title="VPN connection failure",
                description=self.message,
                priority="High",
                category="Network",
                subcategory="VPN",
                assigned_group="Network Support",
            )
        )

        updated = self.service.update_ticket(
            ticket.ticket_id,
            TicketUpdateRequest(
                status="Resolved",
                resolution="Reset the VPN client profile.",
            ),
        )
        similar = self.service.search_similar_tickets(
            "VPN connection failure",
            category="Network",
        )
        status = self.service.get_ticket_status(ticket.ticket_id)

        self.assertEqual(updated.status, "Resolved")
        self.assertEqual(status.status, "Resolved")
        self.assertEqual(similar[0].ticket_id, ticket.ticket_id)
        self.assertEqual(similar[0].resolution, "Reset the VPN client profile.")


class TicketApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_ticket_endpoints_create_update_status_and_search(self) -> None:
        response = self.client.post(
            "/api/tickets",
            json={
                "title": "VPN connection failure",
                "description": "VPN cannot connect after password reset",
                "priority": "High",
                "category": "Network",
                "subcategory": "VPN",
                "assigned_group": "Network Support",
            },
        )

        self.assertEqual(response.status_code, 201)
        ticket = response.json()
        ticket_id = ticket["ticket_id"]
        self.assertEqual(ticket["status"], "Open")

        listing = self.client.get("/api/tickets")
        self.assertEqual(listing.status_code, 200)
        self.assertTrue(any(item["ticket_id"] == ticket_id for item in listing.json()))

        update = self.client.put(
            f"/api/tickets/{ticket_id}",
            json={"status": "Resolved", "resolution": "Reconnected VPN client."},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["status"], "Resolved")

        status_response = self.client.get(f"/api/tickets/status/{ticket_id}")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "Resolved")

        similar = self.client.get(
            "/api/tickets/similar",
            params={"q": "VPN connection failure", "category": "Network"},
        )
        self.assertEqual(similar.status_code, 200)
        self.assertTrue(any(item["ticket_id"] == ticket_id for item in similar.json()))

    def test_approval_endpoint_creates_a_ticket_only_for_pending_recommendation(self) -> None:
        message = "My VPN is not connecting and a meeting starts soon."
        ticket_service.request_ticket_approval(
            message,
            {
                "issue": "VPN connection failure",
                "priority": "High",
                "category": "Network",
                "subcategory": "VPN",
                "assigned_group": "Network Support",
            },
        )

        response = self.client.post(
            "/api/tickets/approve",
            json={
                "approved": True,
                "message": message,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["approved"])
        self.assertEqual(payload["ticket_id"], payload["ticket"]["ticket_id"])
        self.assertEqual(payload["status"], "Open")
        self.assertEqual(payload["assigned_group"], "Network Support")

        missing_approval = self.client.post(
            "/api/tickets/approve",
            json={"approved": True, "message": message, "approval_id": "invalid"},
        )
        self.assertEqual(missing_approval.status_code, 404)

    def test_approval_endpoint_uses_submitted_details_if_pending_state_was_lost(self) -> None:
        message = "My laptop will not turn on."
        response = self.client.post(
            "/api/tickets/approve",
            json={
                "approved": True,
                "message": message,
                "approval_id": "approval-from-prior-process",
                "ticket_details": {
                    "title": "Laptop power failure",
                    "description": message,
                    "priority": "High",
                    "category": "Hardware",
                    "subcategory": "Power",
                    "assigned_group": "Hardware Support",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["approved"])
        self.assertEqual(body["ticket"]["title"], "Laptop power failure")
        self.assertEqual(body["ticket"]["status"], "Open")

    def test_rejected_approval_never_creates_submitted_ticket_details(self) -> None:
        message = "My laptop will not turn on."
        approval_id = ticket_service.request_ticket_approval(
            message,
            {
                "issue": "Laptop power failure",
                "priority": "High",
                "category": "Hardware",
                "subcategory": "Power",
                "assigned_group": "Hardware Support",
            },
        )
        response = self.client.post(
            "/api/tickets/approve",
            json={
                "approved": False,
                "message": message,
                "approval_id": approval_id,
                "ticket_details": {
                    "title": "Laptop power failure",
                    "description": message,
                    "priority": "High",
                    "category": "Hardware",
                    "subcategory": "Power",
                    "assigned_group": "Hardware Support",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["approved"])
        self.assertIsNone(response.json()["ticket"])


if __name__ == "__main__":
    unittest.main()
