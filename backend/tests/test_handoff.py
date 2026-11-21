import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.database.session import get_db
from app.main import app


class HumanHandoffRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

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

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def create_request(self) -> dict:
        return {
            "messages": [
                {
                    "role": "user",
                    "content": "VPN login fails",
                    "timestamp": "2026-11-21T08:00:00Z",
                },
                {
                    "role": "assistant",
                    "content": "I could not find a matching knowledge article.",
                    "metadata": {
                        "agent_response": {
                            "classification": {"category": "Network"},
                            "knowledge_sources": [],
                        }
                    },
                },
            ],
            "context": {
                "classification": {"category": "Network"},
                "knowledge_sources": [],
                "ticket_data": {"priority": "High"},
            },
            "priority": "High",
            "category": "Network",
        }

    def test_create_request_persists_transcript_and_context(self) -> None:
        response = self.client.post(
            "/api/handoff/request",
            json=self.create_request(),
        )

        self.assertEqual(response.status_code, 201)
        conversation = response.json()
        self.assertRegex(conversation["conversation_id"], r"^HUM-[A-F0-9]{8}$")
        self.assertEqual(conversation["status"], "Waiting")
        self.assertEqual(conversation["context"]["ticket_data"]["priority"], "High")
        detail = self.client.get(
            f"/api/handoff/{conversation['conversation_id']}/messages"
        )
        self.assertEqual(
            [message["sender_type"] for message in detail.json()["messages"]],
            ["user", "agent", "system"],
        )
        self.assertIn(
            "agent_response",
            detail.json()["conversation"]["context"]["conversation_history"][1][
                "metadata"
            ],
        )

    def test_accept_poll_send_and_resolve_workflow(self) -> None:
        created = self.client.post(
            "/api/handoff/request",
            json=self.create_request(),
        ).json()
        conversation_id = created["conversation_id"]

        accepted = self.client.post(
            f"/api/handoff/{conversation_id}/accept",
            json={"agent_name": "Alex"},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "In Progress")
        self.assertEqual(accepted.json()["assigned_agent"], "Alex")

        sent = self.client.post(
            f"/api/handoff/{conversation_id}/messages",
            json={"sender_type": "agent", "message": "I can help with VPN access."},
        )
        self.assertEqual(sent.status_code, 201)
        self.assertEqual(sent.json()["sender_type"], "agent")

        queue = self.client.get("/api/handoff/requests?status=In%20Progress")
        self.assertEqual(len(queue.json()), 1)
        self.assertEqual(queue.json()[0]["conversation_id"], conversation_id)
        self.assertNotIn("context", queue.json()[0])

        resolved = self.client.post(f"/api/handoff/{conversation_id}/resolve")
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["status"], "Resolved")
        self.assertEqual(
            self.client.get(f"/api/handoff/{conversation_id}/status").json()[
                "status"
            ],
            "Resolved",
        )

    def test_accept_uses_default_support_engineer_without_body(self) -> None:
        created = self.client.post(
            "/api/handoff/request",
            json=self.create_request(),
        ).json()

        accepted = self.client.post(
            f"/api/handoff/{created['conversation_id']}/accept"
        )

        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["assigned_agent"], "Support Engineer")
