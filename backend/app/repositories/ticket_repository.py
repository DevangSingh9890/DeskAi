import logging
import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models import TicketApprovalRecord, TicketRecord
from app.models.ticket import (
    SimilarTicket,
    Ticket,
    TicketCreateRequest,
    TicketUpdateRequest,
)
from app.services.ticket_errors import (
    PendingApprovalNotFoundError,
    TicketServiceError,
)

logger = logging.getLogger(__name__)
SessionSource = Session | Callable[[], Session]


class TicketRepository:
    def __init__(self, session_source: SessionSource) -> None:
        self._session_source = session_source

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        if isinstance(self._session_source, Session):
            try:
                with self._session_source.begin():
                    yield self._session_source
            except SQLAlchemyError as exc:
                logger.exception("Ticket database operation failed")
                raise TicketServiceError(
                    "Ticket database operation failed."
                ) from exc
            return

        with self._session_source() as session:
            try:
                with session.begin():
                    yield session
            except SQLAlchemyError as exc:
                logger.exception("Ticket database operation failed")
                raise TicketServiceError(
                    "Ticket database operation failed."
                ) from exc

    def create(self, request: TicketCreateRequest) -> Ticket:
        with self._transaction() as session:
            return self._insert_ticket(session, request)

    def get(self, ticket_id: str) -> Ticket | None:
        with self._transaction() as session:
            record = session.scalar(
                select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
            )
            return self._to_ticket(record) if record is not None else None

    def list_tickets(self) -> list[Ticket]:
        with self._transaction() as session:
            records = session.scalars(
                select(TicketRecord).order_by(TicketRecord.created_at.desc())
            ).all()
            return [self._to_ticket(record) for record in records]

    def update(
        self, ticket_id: str, changes: Mapping[str, object]
    ) -> Ticket | None:
        with self._transaction() as session:
            record = session.scalar(
                select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
            )
            if record is None:
                return None

            for field, value in changes.items():
                setattr(record, field, value)
            record.updated_at = datetime.now(timezone.utc)
            session.flush()
            return self._to_ticket(record)

    def search_similar(
        self,
        query: str,
        *,
        category: str | None = None,
        priority: str | None = None,
        limit: int = 5,
    ) -> list[SimilarTicket]:
        terms = set(re.findall(r"[a-z0-9]+", query.casefold()))
        if not terms:
            return []

        with self._transaction() as session:
            conditions = [
                column.ilike(f"%{term}%")
                for term in terms
                for column in (
                    TicketRecord.title,
                    TicketRecord.description,
                    TicketRecord.category,
                    TicketRecord.subcategory,
                    TicketRecord.resolution,
                )
            ]
            statement = select(TicketRecord).where(or_(*conditions))
            if priority:
                statement = statement.where(TicketRecord.priority == priority)
            records = session.scalars(statement).all()

            ranked: list[tuple[int, TicketRecord]] = []
            for record in records:
                searchable_text = " ".join(
                    (
                        record.title,
                        record.description,
                        record.category,
                        record.subcategory,
                        record.resolution or "",
                    )
                ).casefold()
                record_terms = set(re.findall(r"[a-z0-9]+", searchable_text))
                score = len(terms & record_terms)
                if category and record.category.casefold() == category.casefold():
                    score += 3
                if score:
                    ranked.append((score, record))

            ranked.sort(
                key=lambda item: (item[0], item[1].created_at),
                reverse=True,
            )
            return [
                SimilarTicket(
                    ticket_id=record.ticket_id,
                    category=record.category,
                    priority=record.priority,
                    summary=record.title,
                    resolution=record.resolution,
                )
                for _, record in ranked[:limit]
            ]

    def create_approval(
        self,
        approval_id: str,
        message: str,
        request: TicketCreateRequest,
        expires_at: datetime,
    ) -> None:
        with self._transaction() as session:
            session.execute(
                delete(TicketApprovalRecord).where(
                    TicketApprovalRecord.expires_at <= datetime.now(timezone.utc)
                )
            )
            session.add(
                TicketApprovalRecord(
                    approval_id=approval_id,
                    message=message,
                    ticket_data=request.model_dump(mode="json"),
                    expires_at=expires_at,
                )
            )

    def approve(self, approval_id: str | None, message: str) -> Ticket:
        with self._transaction() as session:
            approval = self._find_approval(session, approval_id, message)
            request = TicketCreateRequest.model_validate(approval.ticket_data)
            ticket = self._insert_ticket(session, request)
            session.delete(approval)
            return ticket

    def reject(self, approval_id: str | None, message: str) -> None:
        with self._transaction() as session:
            approval = self._find_approval(session, approval_id, message)
            session.delete(approval)

    def analytics(self) -> dict[str, Any]:
        with self._transaction() as session:
            total = session.scalar(select(func.count()).select_from(TicketRecord)) or 0
            status_counts = dict(
                session.execute(
                    select(TicketRecord.status, func.count())
                    .group_by(TicketRecord.status)
                ).all()
            )
            priority_counts = dict(
                session.execute(
                    select(TicketRecord.priority, func.count())
                    .group_by(TicketRecord.priority)
                ).all()
            )
            return {
                "total_tickets": total,
                "open_tickets": status_counts.get("Open", 0)
                + status_counts.get("In Progress", 0),
                "resolved_tickets": status_counts.get("Resolved", 0),
                "high_priority_tickets": priority_counts.get("High", 0)
                + priority_counts.get("Critical", 0),
                "by_status": status_counts,
                "by_priority": priority_counts,
            }

    @staticmethod
    def _insert_ticket(session: Session, request: TicketCreateRequest) -> Ticket:
        record = TicketRecord(
            ticket_id=f"PENDING-{token_urlsafe(12)}",
            title=request.title,
            description=request.description,
            category=request.category,
            subcategory=request.subcategory,
            priority=request.priority,
            status="Open",
            assigned_group=request.assigned_group,
            created_by=request.created_by,
        )
        session.add(record)
        session.flush()
        record.ticket_id = f"INC-{record.id + 10000:05d}"
        session.flush()
        return TicketRepository._to_ticket(record)

    @staticmethod
    def _find_approval(
        session: Session,
        approval_id: str | None,
        message: str,
    ) -> TicketApprovalRecord:
        now = datetime.now(timezone.utc)
        if approval_id is not None:
            approval = session.scalar(
                select(TicketApprovalRecord)
                .where(TicketApprovalRecord.approval_id == approval_id)
                .with_for_update()
            )
            if approval is not None:
                expires_at = approval.expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if approval.message != message or expires_at <= now:
                    raise PendingApprovalNotFoundError(
                        "No pending ticket recommendation matches this approval."
                    )
                return approval

        approval = session.scalar(
            select(TicketApprovalRecord)
            .where(
                TicketApprovalRecord.message == message,
                TicketApprovalRecord.expires_at > now,
            )
            .order_by(TicketApprovalRecord.expires_at.desc())
            .with_for_update()
        )
        if approval is None:
            raise PendingApprovalNotFoundError(
                "No pending ticket recommendation matches this approval."
            )
        return approval

    @staticmethod
    def _to_ticket(record: TicketRecord) -> Ticket:
        return Ticket(
            ticket_id=record.ticket_id,
            title=record.title,
            description=record.description,
            priority=record.priority,
            status=record.status,
            category=record.category,
            subcategory=record.subcategory,
            assigned_group=record.assigned_group,
            created_at=record.created_at,
            updated_at=record.updated_at,
            created_by=record.created_by,
            resolution=record.resolution,
        )
