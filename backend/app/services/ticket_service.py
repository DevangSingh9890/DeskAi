import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from threading import RLock
from typing import Protocol

from app.models.ticket import (
    SimilarTicket,
    Ticket,
    TicketCreateRequest,
    TicketStatusResponse,
    TicketUpdateRequest,
)

logger = logging.getLogger(__name__)


class TicketServiceError(RuntimeError):
    pass


class TicketNotFoundError(TicketServiceError):
    pass


class PendingApprovalNotFoundError(TicketServiceError):
    pass


class TicketRepository(Protocol):
    def create(self, request: TicketCreateRequest) -> Ticket: ...

    def get(self, ticket_id: str) -> Ticket | None: ...

    def list(self) -> list[Ticket]: ...

    def update(self, ticket_id: str, changes: Mapping[str, object]) -> Ticket | None: ...


class InMemoryTicketRepository:
    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._next_number = 10001
        self._lock = RLock()

    def create(self, request: TicketCreateRequest) -> Ticket:
        with self._lock:
            now = datetime.now(timezone.utc)
            ticket = Ticket(
                ticket_id=f"INC-{self._next_number:05d}",
                title=request.title,
                description=request.description,
                priority=request.priority,
                status="Open",
                category=request.category,
                subcategory=request.subcategory,
                assigned_group=request.assigned_group,
                created_at=now,
                updated_at=now,
                created_by=request.created_by,
            )
            self._next_number += 1
            self._tickets[ticket.ticket_id] = ticket
            return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        with self._lock:
            return self._tickets.get(ticket_id)

    def list(self) -> list[Ticket]:
        with self._lock:
            return sorted(
                self._tickets.values(),
                key=lambda ticket: ticket.created_at,
                reverse=True,
            )

    def update(self, ticket_id: str, changes: Mapping[str, object]) -> Ticket | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None
            updated = ticket.model_copy(
                update={
                    **changes,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._tickets[ticket_id] = updated
            return updated


@dataclass(frozen=True)
class PendingApproval:
    message: str
    request: TicketCreateRequest
    expires_at: datetime


class TicketService:
    def __init__(
        self,
        repository: TicketRepository | None = None,
        approval_ttl: timedelta = timedelta(minutes=30),
    ) -> None:
        self._repository = repository or InMemoryTicketRepository()
        self._approval_ttl = approval_ttl
        self._pending_approvals: dict[str, PendingApproval] = {}
        self._lock = RLock()

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
        return self._repository.list()

    def update_ticket(
        self, ticket_id: str, request: TicketUpdateRequest
    ) -> Ticket:
        changes = request.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("At least one ticket field must be provided.")
        ticket = self._repository.update(ticket_id, changes)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found.")
        logger.info("Ticket Updated ticket_id=%s", ticket.ticket_id)
        return ticket

    def assign_ticket(self, ticket_id: str, assigned_group: str) -> Ticket:
        return self.update_ticket(
            ticket_id,
            TicketUpdateRequest(assigned_group=assigned_group),
        )

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
        query_terms = set(re.findall(r"[a-z0-9]+", query.casefold()))
        ranked: list[tuple[int, Ticket]] = []
        for ticket in self._repository.list():
            if priority and ticket.priority != priority:
                continue
            searchable_text = " ".join(
                (
                    ticket.title,
                    ticket.description,
                    ticket.category,
                    ticket.subcategory,
                    ticket.resolution or "",
                )
            ).casefold()
            ticket_terms = set(re.findall(r"[a-z0-9]+", searchable_text))
            score = len(query_terms & ticket_terms)
            if category and ticket.category.casefold() == category.casefold():
                score += 3
            if score:
                ranked.append((score, ticket))

        ranked.sort(
            key=lambda item: (item[0], item[1].created_at),
            reverse=True,
        )
        return [
            SimilarTicket(
                ticket_id=ticket.ticket_id,
                category=ticket.category,
                priority=ticket.priority,
                summary=ticket.title,
                resolution=ticket.resolution,
            )
            for _, ticket in ranked[:limit]
        ]

    def request_ticket_approval(
        self, message: str, classification: Mapping[str, object]
    ) -> str:
        request = TicketCreateRequest(
            title=str(classification["issue"]),
            description=message,
            priority=classification["priority"],
            category=str(classification["category"]),
            subcategory=str(classification["subcategory"]),
            assigned_group=str(classification["assigned_group"]),
            created_by="user",
        )
        approval_id = token_urlsafe(24)
        now = datetime.now(timezone.utc)
        with self._lock:
            self._discard_expired_approvals(now)
            self._pending_approvals[approval_id] = PendingApproval(
                message=message,
                request=request,
                expires_at=now + self._approval_ttl,
            )
        logger.info("Approval Requested approval_id=%s", approval_id)
        return approval_id

    def approve_ticket(self, approval_id: str | None, message: str) -> Ticket:
        with self._lock:
            pending_id, pending = self._find_pending_approval(approval_id, message)
            ticket = self.create_ticket(pending.request)
            del self._pending_approvals[pending_id]
            return ticket

    def reject_ticket_approval(
        self, approval_id: str | None, message: str
    ) -> None:
        with self._lock:
            pending_id, _ = self._find_pending_approval(approval_id, message)
            del self._pending_approvals[pending_id]

    def _find_pending_approval(
        self, approval_id: str | None, message: str
    ) -> tuple[str, PendingApproval]:
        self._discard_expired_approvals(datetime.now(timezone.utc))
        if approval_id is not None:
            pending = self._pending_approvals.get(approval_id)
            if pending is not None:
                if pending.message != message:
                    raise PendingApprovalNotFoundError(
                        "No pending ticket recommendation matches this approval."
                    )
                return approval_id, pending

            for pending_id, pending in reversed(self._pending_approvals.items()):
                if pending.message == message:
                    logger.warning(
                        "Approval ID was stale; matched pending approval by message"
                    )
                    return pending_id, pending

            raise PendingApprovalNotFoundError(
                "No pending ticket recommendation matches this approval."
            )

        for pending_id, pending in reversed(self._pending_approvals.items()):
            if pending.message == message:
                return pending_id, pending

        raise PendingApprovalNotFoundError(
            "No pending ticket recommendation matches this message."
        )

    def _discard_expired_approvals(self, now: datetime) -> None:
        expired = [
            approval_id
            for approval_id, approval in self._pending_approvals.items()
            if approval.expires_at <= now
        ]
        for approval_id in expired:
            del self._pending_approvals[approval_id]


ticket_service = TicketService()
