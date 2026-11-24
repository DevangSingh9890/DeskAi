import logging
import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models import (
    TicketApprovalRecord,
    TicketCommentRecord,
    TicketHistoryRecord,
    TicketRecord,
    TicketSequenceRecord,
)
from app.models.ticket import (
    AdminTicketDetail,
    SimilarTicket,
    Ticket,
    TicketComment,
    TicketCreateRequest,
    TicketHistory,
    TicketUpdateRequest,
)
from app.services.ticket_errors import (
    PendingApprovalNotFoundError,
    TicketServiceError,
)

logger = logging.getLogger(__name__)
SessionSource = Session | Callable[[], Session]
INCIDENT_KEYWORDS = (
    "issue", "error", "failed", "failure", "broken", "crash", "cannot",
    "unable", "problem", "outage", "login issue", "vpn not working",
    "application issue", "not working", "inaccessible", "degraded",
)
SERVICE_REQUEST_KEYWORDS = (
    "request", "install", "installation", "access", "permission", "account",
    "create", "onboarding", "software request", "hardware request",
    "provision", "setup",
)


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
        sort_columns = {
            "ticket_id": TicketRecord.ticket_id,
            "title": TicketRecord.title,
            "priority": TicketRecord.priority,
            "status": TicketRecord.status,
            "category": TicketRecord.category,
            "assigned_group": TicketRecord.assigned_group,
            "created_at": TicketRecord.created_at,
            "updated_at": TicketRecord.updated_at,
        }
        with self._transaction() as session:
            statement = select(TicketRecord)
            if search:
                term = f"%{search.strip()}%"
                statement = statement.where(
                    or_(
                        TicketRecord.ticket_id.ilike(term),
                        TicketRecord.title.ilike(term),
                        TicketRecord.description.ilike(term),
                        TicketRecord.category.ilike(term),
                        TicketRecord.subcategory.ilike(term),
                        TicketRecord.assigned_group.ilike(term),
                    )
                )
            if ticket_status:
                statement = statement.where(TicketRecord.status == ticket_status)
            if priority:
                statement = statement.where(TicketRecord.priority == priority)
            if assignment_group:
                statement = statement.where(
                    TicketRecord.assigned_group == assignment_group
                )

            total = session.scalar(
                select(func.count()).select_from(statement.subquery())
            ) or 0
            sort_column = sort_columns[sort_by]
            ordering = sort_column.asc() if sort_order == "asc" else sort_column.desc()
            records = session.scalars(
                statement.order_by(ordering, TicketRecord.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "items": [self._to_ticket(record) for record in records],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            }

    def update(
        self,
        ticket_id: str,
        changes: Mapping[str, object],
        *,
        actor: str = "System",
    ) -> Ticket | None:
        with self._transaction() as session:
            record = session.scalar(
                select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
            )
            if record is None:
                return None

            if "status" in changes and changes["status"] != record.status:
                session.add(
                    TicketHistoryRecord(
                        ticket_id=ticket_id,
                        event_type="status_changed",
                        old_value=record.status,
                        new_value=str(changes["status"]),
                        actor=actor,
                    )
                )
            if (
                "assigned_group" in changes
                and changes["assigned_group"] != record.assigned_group
            ):
                session.add(
                    TicketHistoryRecord(
                        ticket_id=ticket_id,
                        event_type="assignment_changed",
                        old_value=record.assigned_group,
                        new_value=str(changes["assigned_group"]),
                        actor=actor,
                    )
                )
            for field, value in changes.items():
                setattr(record, field, value)
            record.updated_at = datetime.now(timezone.utc)
            session.flush()
            return self._to_ticket(record)

    def get_admin_details(self, ticket_id: str) -> AdminTicketDetail | None:
        with self._transaction() as session:
            record = session.scalar(
                select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
            )
            if record is None:
                return None
            comments = session.scalars(
                select(TicketCommentRecord)
                .where(TicketCommentRecord.ticket_id == ticket_id)
                .order_by(TicketCommentRecord.created_at, TicketCommentRecord.id)
            ).all()
            history = session.scalars(
                select(TicketHistoryRecord)
                .where(TicketHistoryRecord.ticket_id == ticket_id)
                .order_by(TicketHistoryRecord.created_at, TicketHistoryRecord.id)
            ).all()
            return AdminTicketDetail(
                **self._to_ticket(record).model_dump(),
                comments=[self._to_comment(item) for item in comments],
                history=[self._to_history(item) for item in history],
            )

    def list_comments(self, ticket_id: str) -> list[TicketComment] | None:
        with self._transaction() as session:
            exists = session.scalar(
                select(TicketRecord.id).where(TicketRecord.ticket_id == ticket_id)
            )
            if exists is None:
                return None
            comments = session.scalars(
                select(TicketCommentRecord)
                .where(TicketCommentRecord.ticket_id == ticket_id)
                .order_by(TicketCommentRecord.created_at, TicketCommentRecord.id)
            ).all()
            return [self._to_comment(item) for item in comments]

    def add_comment(
        self, ticket_id: str, body: str, author: str
    ) -> TicketComment | None:
        with self._transaction() as session:
            ticket = session.scalar(
                select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
            )
            if ticket is None:
                return None
            ticket.updated_at = datetime.now(timezone.utc)
            comment = TicketCommentRecord(
                ticket_id=ticket_id,
                body=body,
                author=author,
            )
            session.add(comment)
            session.add(
                TicketHistoryRecord(
                    ticket_id=ticket_id,
                    event_type="comment_added",
                    new_value="Comment added",
                    actor=author,
                )
            )
            session.flush()
            return self._to_comment(comment)

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
                    ticket_number=(
                        record.ticket_number
                        or (
                            record.ticket_id
                            if record.ticket_id.startswith(("INC-", "SR-", "HUM-"))
                            else None
                        )
                    ),
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
            category_counts = dict(
                session.execute(
                    select(TicketRecord.category, func.count())
                    .group_by(TicketRecord.category)
                ).all()
            )
            assignment_counts = dict(
                session.execute(
                    select(TicketRecord.assigned_group, func.count())
                    .group_by(TicketRecord.assigned_group)
                ).all()
            )
            today = datetime.now(timezone.utc).date()
            start_day = today - timedelta(days=6)
            daily_counts = {
                str(day): count
                for day, count in session.execute(
                    select(func.date(TicketRecord.created_at), func.count())
                    .where(TicketRecord.created_at >= start_day)
                    .group_by(func.date(TicketRecord.created_at))
                ).all()
            }
            tickets_created_by_day = [
                {
                    "date": (start_day + timedelta(days=offset)).isoformat(),
                    "count": daily_counts.get(
                        (start_day + timedelta(days=offset)).isoformat(), 0
                    ),
                }
                for offset in range(7)
            ]
            return {
                "total_tickets": total,
                "open_tickets": status_counts.get("Open", 0)
                + status_counts.get("In Progress", 0),
                "resolved_tickets": status_counts.get("Resolved", 0),
                "high_priority_tickets": priority_counts.get("High", 0)
                + priority_counts.get("Critical", 0),
                "by_status": status_counts,
                "by_priority": priority_counts,
                "ticket_categories": [
                    {"name": name, "count": count}
                    for name, count in category_counts.items()
                ],
                "priority_distribution": [
                    {"name": name, "count": count}
                    for name, count in priority_counts.items()
                ],
                "status_distribution": [
                    {"name": name, "count": count}
                    for name, count in status_counts.items()
                ],
                "tickets_created_by_day": tickets_created_by_day,
                "assigned_group_distribution": [
                    {"name": name, "count": count}
                    for name, count in assignment_counts.items()
                ],
            }

    @staticmethod
    def _determine_ticket_type(request: TicketCreateRequest) -> str:
        if request.ticket_type in ("incident", "service_request"):
            return request.ticket_type

        text = " ".join(
            (
                request.title,
                request.description,
                request.category,
                request.subcategory,
                request.ai_recommendation or "",
            )
        ).casefold()

        if (
            request.category.casefold() == "access management"
            or "password reset" in text
        ):
            return "service_request"
        if any(
            keyword in text
            for keyword in (
                "install ",
                "installation",
                "software request",
                "hardware request",
                "request",
                "permission",
                "onboarding",
                "provision",
                "setup",
            )
        ):
            return "service_request"
        incident_matches = [
            keyword for keyword in INCIDENT_KEYWORDS
            if keyword in text
        ]
        if incident_matches:
            return "incident"
        if any(keyword in text for keyword in SERVICE_REQUEST_KEYWORDS):
            return "service_request"
        return "incident"

    @staticmethod
    def _insert_ticket(session: Session, request: TicketCreateRequest) -> Ticket:
        ticket_type = TicketRepository._determine_ticket_type(request)
        record = TicketRecord(
            ticket_id=f"PENDING-{token_urlsafe(12)}",
            ticket_type=ticket_type,
            title=request.title,
            description=request.description,
            category=request.category,
            subcategory=request.subcategory,
            priority=request.priority,
            status="Open",
            assigned_group=request.assigned_group,
            created_by=request.created_by,
            impact=request.impact or TicketRepository._impact_for_priority(
                request.priority
            ),
            ai_recommendation=request.ai_recommendation,
            knowledge_sources=request.knowledge_sources,
            similar_incidents=request.similar_incidents,
        )
        session.add(record)
        session.flush()
        prefix = "INC" if ticket_type == "incident" else "SR"
        sequence = session.scalar(
            select(TicketSequenceRecord)
            .where(TicketSequenceRecord.ticket_type == ticket_type)
            .with_for_update()
        )
        if sequence is None:
            sequence = TicketSequenceRecord(ticket_type=ticket_type, last_number=0)
            session.add(sequence)
            session.flush()
        sequence.last_number += 1
        record.ticket_number = f"{prefix}-{sequence.last_number:05d}"
        record.ticket_id = record.ticket_number
        session.flush()
        session.add(
            TicketHistoryRecord(
                ticket_id=record.ticket_id,
                event_type="ticket_created",
                new_value=record.title,
                actor=record.created_by,
            )
        )
        session.add(
            TicketHistoryRecord(
                ticket_id=record.ticket_id,
                event_type="assignment_changed",
                new_value=record.assigned_group,
                actor=record.created_by,
            )
        )
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
            ticket_type=(
                record.ticket_type
                if record.ticket_type in ("incident", "service_request")
                else None
            ),
            ticket_number=(
                record.ticket_number
                or (
                    record.ticket_id
                    if record.ticket_id.startswith(("INC-", "SR-", "HUM-"))
                    else None
                )
            ),
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
            impact=record.impact or TicketRepository._impact_for_priority(
                record.priority
            ),
            ai_recommendation=record.ai_recommendation,
            knowledge_sources=record.knowledge_sources or [],
            similar_incidents=record.similar_incidents or [],
        )

    @staticmethod
    def _impact_for_priority(priority: str) -> str:
        return {
            "Critical": "High",
            "High": "High",
            "Medium": "Medium",
            "Low": "Low",
        }.get(priority, "Medium")

    @staticmethod
    def _to_comment(record: TicketCommentRecord) -> TicketComment:
        return TicketComment(
            id=record.id,
            ticket_id=record.ticket_id,
            author=record.author,
            body=record.body,
            created_at=record.created_at,
        )

    @staticmethod
    def _to_history(record: TicketHistoryRecord) -> TicketHistory:
        return TicketHistory(
            id=record.id,
            ticket_id=record.ticket_id,
            event_type=record.event_type,
            old_value=record.old_value,
            new_value=record.new_value,
            actor=record.actor,
            created_at=record.created_at,
        )
