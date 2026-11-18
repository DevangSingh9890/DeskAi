import logging
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any

from app.database.session import SessionLocal
from app.models.ticket import (
    AdminTicketDetail,
    SimilarTicket,
    Ticket,
    TicketComment,
    TicketCreateRequest,
    TicketStatusResponse,
    TicketUpdateRequest,
)
from app.repositories.ticket_repository import TicketRepository
from app.services.ticket_errors import (
    PendingApprovalNotFoundError,
    TicketNotFoundError,
    TicketServiceError,
)

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(
        self,
        repository: TicketRepository | None = None,
        approval_ttl: timedelta = timedelta(minutes=30),
    ) -> None:
        self._repository = repository or TicketRepository(SessionLocal)
        self._approval_ttl = approval_ttl

    def create_ticket(self, request: TicketCreateRequest) -> Ticket:
        ticket = self._repository.create(request)
        logger.info("Ticket Created ticket_id=%s", ticket.ticket_id)
        return ticket

    def get_ticket(self, ticket_id: str) -> Ticket:
        ticket = self._repository.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found.")
        return ticket

    def list_tickets(self) -> list[Ticket]:
        return self._repository.list_tickets()

    def list_admin_tickets(
        self,
        *,
        search: str | None,
        ticket_status: str | None,
        priority: str | None,
        assignment_group: str | None,
        sort_by: str,
        sort_order: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        return self._repository.list_admin_tickets(
            search=search,
            ticket_status=ticket_status,
            priority=priority,
            assignment_group=assignment_group,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    def get_admin_ticket(self, ticket_id: str) -> AdminTicketDetail:
        ticket = self._repository.get_admin_details(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found.")
        return ticket

    def update_ticket(
        self,
        ticket_id: str,
        request: TicketUpdateRequest,
        *,
        actor: str = "System",
    ) -> Ticket:
        changes = request.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("At least one ticket field must be provided.")
        ticket = self._repository.update(ticket_id, changes, actor=actor)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found.")
        logger.info("Ticket Updated ticket_id=%s", ticket.ticket_id)
        return ticket

    def assign_ticket(
        self,
        ticket_id: str,
        assigned_group: str,
        *,
        actor: str = "System",
    ) -> Ticket:
        return self.update_ticket(
            ticket_id,
            TicketUpdateRequest(assigned_group=assigned_group),
            actor=actor,
        )

    def list_ticket_comments(self, ticket_id: str) -> list[TicketComment]:
        comments = self._repository.list_comments(ticket_id)
        if comments is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found.")
        return comments

    def add_ticket_comment(
        self, ticket_id: str, body: str, author: str
    ) -> TicketComment:
        comment = self._repository.add_comment(ticket_id, body, author)
        if comment is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found.")
        return comment

    def get_ticket_status(self, ticket_id: str) -> TicketStatusResponse:
        ticket = self.get_ticket(ticket_id)
        logger.info("Ticket Status Retrieved ticket_id=%s", ticket_id)
        return TicketStatusResponse(
            ticket_id=ticket.ticket_id,
            status=ticket.status,
            assigned_group=ticket.assigned_group,
            updated_at=ticket.updated_at,
        )

    def search_similar_tickets(
        self,
        query: str,
        *,
        category: str | None = None,
        priority: str | None = None,
        limit: int = 5,
    ) -> list[SimilarTicket]:
        logger.info("Similar Incidents Searched query=%r", query[:160])
        return self._repository.search_similar(
            query,
            category=category,
            priority=priority,
            limit=limit,
        )

    def request_ticket_approval(
        self,
        message: str,
        classification: Mapping[str, object],
        *,
        knowledge_sources: list[str] | None = None,
        similar_incidents: list[dict[str, Any]] | None = None,
        ai_recommendation: str | None = None,
    ) -> str:
        request = TicketCreateRequest(
            title=str(classification["issue"]),
            description=message,
            priority=classification["priority"],
            category=str(classification["category"]),
            subcategory=str(classification["subcategory"]),
            assigned_group=str(classification["assigned_group"]),
            created_by="user",
            impact=(
                str(classification["impact"])
                if classification.get("impact") is not None
                else None
            ),
            ai_recommendation=ai_recommendation,
            knowledge_sources=knowledge_sources or [],
            similar_incidents=similar_incidents or [],
        )
        approval_id = token_urlsafe(24)
        now = datetime.now(timezone.utc)
        self._repository.create_approval(
            approval_id,
            message,
            request,
            now + self._approval_ttl,
        )
        logger.info("Approval Requested approval_id=%s", approval_id)
        return approval_id

    def approve_ticket(self, approval_id: str | None, message: str) -> Ticket:
        ticket = self._repository.approve(approval_id, message)
        logger.info("Ticket Created ticket_id=%s after approval", ticket.ticket_id)
        return ticket

    def reject_ticket_approval(
        self, approval_id: str | None, message: str
    ) -> None:
        self._repository.reject(approval_id, message)
        logger.info("Ticket recommendation rejected")

    def get_analytics(self) -> dict[str, Any]:
        return self._repository.analytics()


ticket_service = TicketService()
