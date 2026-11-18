import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.database import Base
from app.database.session import get_db
from app.main import app
from app.models.ticket import (
    TicketCreateRequest,
    TicketUpdateRequest,
)
from app.repositories.ticket_repository import TicketRepository
from app.services.ticket_service import (
    PendingApprovalNotFoundError,
    TicketService,
)


def enforce_sqlite_foreign_keys(engine) -> None:
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class TicketServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        enforce_sqlite_foreign_keys(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        Base.metadata.create_all(bind=self.engine)
        self.service = TicketService(TicketRepository(self.session_factory))
        self.message = "My VPN is not connecting"
        self.classification = {
            "issue": "VPN connection failure",
            "priority": "High",
            "category": "Network",
            "subcategory": "VPN",
            "assigned_group": "Network Support",
        }

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_ticket_is_created_only_after_matching_approval(self) -> None:
        approval_id = self.service.request_ticket_approval(
            self.message,
            self.classification,
        )

        self.assertEqual(self.service.list_tickets(), [])
        restarted_service = TicketService(TicketRepository(self.session_factory))
        ticket = restarted_service.approve_ticket(approval_id, self.message)

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

    def test_approval_persists_ai_context_on_created_ticket(self) -> None:
        incident = {
            "ticket_id": "INC-10020",
            "category": "Network",
            "priority": "High",
            "summary": "VPN login failure",
            "resolution": "Reset the client profile.",
        }
        approval_id = self.service.request_ticket_approval(
            self.message,
            {**self.classification, "impact": "Multiple Users"},
            knowledge_sources=["vpn-guide.pdf"],
            similar_incidents=[incident],
            ai_recommendation="Reset the VPN profile and retry.",
        )

        ticket = self.service.approve_ticket(approval_id, self.message)

        self.assertEqual(ticket.impact, "Multiple Users")
        self.assertEqual(ticket.ai_recommendation, "Reset the VPN profile and retry.")
        self.assertEqual(ticket.knowledge_sources, ["vpn-guide.pdf"])
        self.assertEqual(ticket.similar_incidents, [incident])

    def test_rejected_recommendation_does_not_create_ticket(self) -> None:
        approval_id = self.service.request_ticket_approval(
            self.message,
            self.classification,
        )

        self.service.reject_ticket_approval(approval_id, self.message)

        self.assertEqual(self.service.list_tickets(), [])
        with self.assertRaises(PendingApprovalNotFoundError):
            self.service.approve_ticket(approval_id, self.message)

    def test_tickets_survive_service_recreation_and_multiple_creates(self) -> None:
        first = self.service.create_ticket(
            TicketCreateRequest(
                title="VPN connection failure",
                description=self.message,
                priority="High",
                category="Network",
                subcategory="VPN",
                assigned_group="Network Support",
            )
        )
        second = self.service.create_ticket(
            TicketCreateRequest(
                title="Laptop power failure",
                description="Laptop will not power on.",
                priority="Critical",
                category="Hardware",
                subcategory="Power",
                assigned_group="Hardware Support",
            )
        )

        restarted_service = TicketService(TicketRepository(self.session_factory))

        self.assertEqual(
            {ticket.ticket_id for ticket in restarted_service.list_tickets()},
            {first.ticket_id, second.ticket_id},
        )
        self.assertEqual(restarted_service.get_ticket(first.ticket_id), first)

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

        restarted_service = TicketService(TicketRepository(self.session_factory))
        persisted_status = restarted_service.get_ticket_status(ticket.ticket_id)
        self.assertEqual(persisted_status.status, "Resolved")


class TicketApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        enforce_sqlite_foreign_keys(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            database = self.session_factory()
            try:
                yield database
            finally:
                database.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.service = TicketService(TicketRepository(self.session_factory))

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

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
        self.service.request_ticket_approval(
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
        approval_id = self.service.request_ticket_approval(
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

    def test_admin_ticket_apis_and_analytics(self) -> None:
        created = self.client.post(
            "/api/tickets",
            json={
                "title": "VPN connection failure",
                "description": "VPN fails after password reset.",
                "priority": "High",
                "category": "Network",
                "subcategory": "VPN",
                "assigned_group": "Network Support",
            },
        )
        ticket_id = created.json()["ticket_id"]

        listed = self.client.get("/api/admin/tickets")
        detail = self.client.get(f"/api/admin/tickets/{ticket_id}")
        updated = self.client.put(
            f"/api/admin/tickets/{ticket_id}",
            json={"status": "Resolved", "resolution": "Reset VPN profile."},
        )
        analytics = self.client.get("/api/admin/analytics")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(detail.json()["ticket_id"], ticket_id)
        self.assertEqual(updated.json()["status"], "Resolved")
        self.assertEqual(analytics.json()["total_tickets"], 1)
        self.assertEqual(analytics.json()["resolved_tickets"], 1)

    def test_admin_operations_persist_comments_history_and_assignment(self) -> None:
        created = self.client.post(
            "/api/tickets",
            json={
                "title": "Email access failure",
                "description": "Cannot access the service mailbox.",
                "priority": "High",
                "category": "Email",
                "subcategory": "Mailbox access",
                "assigned_group": "Email Support",
                "knowledge_sources": ["mailbox-guide.pdf"],
                "ai_recommendation": "Check the account and mailbox permissions.",
            },
        )
        self.assertEqual(created.status_code, 201)
        ticket_id = created.json()["ticket_id"]

        page = self.client.get(
            "/api/admin/tickets",
            params={"search": "mailbox", "page": 1, "page_size": 1},
        )
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.json()["total"], 1)
        self.assertEqual(page.json()["items"][0]["ticket_id"], ticket_id)

        status_response = self.client.put(
            f"/api/admin/tickets/{ticket_id}/status",
            json={"status": "In Progress"},
        )
        assignment_response = self.client.put(
            f"/api/admin/tickets/{ticket_id}/assign",
            json={"assigned_group": "Identity & Access Management"},
        )
        comment_response = self.client.post(
            f"/api/admin/tickets/{ticket_id}/comments",
            json={"body": "Account access is being investigated."},
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(assignment_response.status_code, 200)
        self.assertEqual(comment_response.status_code, 201)
        details = self.client.get(f"/api/admin/tickets/{ticket_id}")
        comments = self.client.get(f"/api/admin/tickets/{ticket_id}/comments")
        self.assertEqual(details.status_code, 200)
        self.assertEqual(details.json()["status"], "In Progress")
        self.assertEqual(
            details.json()["assigned_group"],
            "Identity & Access Management",
        )
        self.assertEqual(details.json()["knowledge_sources"], ["mailbox-guide.pdf"])
        self.assertEqual(details.json()["comments"][0]["body"], "Account access is being investigated.")
        self.assertEqual(comments.json()[0]["body"], "Account access is being investigated.")
        self.assertEqual(
            {entry["event_type"] for entry in details.json()["history"]},
            {"ticket_created", "status_changed", "assignment_changed", "comment_added"},
        )

        dashboard = self.client.get("/api/admin/dashboard")
        analytics = self.client.get("/api/admin/analytics")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["total_tickets"], 1)
        self.assertEqual(analytics.status_code, 200)
        self.assertEqual(analytics.json()["ticket_categories"][0]["name"], "Email")
        self.assertEqual(analytics.json()["tickets_created_by_day"][-1]["count"], 1)

    def test_admin_assignment_rejects_unsupported_group(self) -> None:
        created = self.client.post(
            "/api/tickets",
            json={
                "title": "Laptop failure",
                "description": "Laptop will not start.",
                "priority": "Medium",
                "category": "Hardware",
                "subcategory": "Power",
                "assigned_group": "Hardware Support",
            },
        )
        ticket_id = created.json()["ticket_id"]
        response = self.client.put(
            f"/api/admin/tickets/{ticket_id}/assign",
            json={"assigned_group": "Unknown Team"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
