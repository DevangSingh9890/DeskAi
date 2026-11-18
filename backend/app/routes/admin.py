import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.ticket import (
    ADMIN_ASSIGNMENT_GROUPS,
    AdminTicketDetail,
    Ticket,
    TicketAssignmentRequest,
    TicketComment,
    TicketCommentCreateRequest,
    TicketPriority,
    TicketStatus,
    TicketStatusUpdateRequest,
    TicketUpdateRequest,
)
from app.repositories.ticket_repository import TicketRepository
from app.services.file_service import DocumentStorageError, list_documents
from app.services.ticket_errors import TicketNotFoundError, TicketServiceError
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_admin_ticket_service(database: Session = Depends(get_db)) -> TicketService:
    return TicketService(TicketRepository(database))


@router.get("/dashboard")
def admin_dashboard(
    service: TicketService = Depends(get_admin_ticket_service),
) -> dict[str, int]:
    try:
        metrics = service.get_analytics()
        documents = list_documents()
    except (TicketServiceError, DocumentStorageError) as exc:
        logger.exception("Admin dashboard data could not be loaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dashboard data is unavailable.",
        ) from exc
    return {
        "total_tickets": metrics["total_tickets"],
        "open_tickets": metrics["open_tickets"],
        "resolved_tickets": metrics["resolved_tickets"],
        "high_priority_tickets": metrics["high_priority_tickets"],
        "knowledge_documents": len(documents),
    }


@router.get("/tickets")
def admin_list_tickets(
    search: str | None = Query(default=None, max_length=200),
    ticket_status: TicketStatus | None = Query(default=None, alias="status"),
    priority: TicketPriority | None = None,
    assignment_group: str | None = Query(default=None, max_length=150),
    sort_by: Literal[
        "ticket_id",
        "title",
        "priority",
        "status",
        "category",
        "assigned_group",
        "created_at",
        "updated_at",
    ] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    service: TicketService = Depends(get_admin_ticket_service),
) -> dict[str, object]:
    try:
        return service.list_admin_tickets(
            search=search,
            ticket_status=ticket_status,
            priority=priority,
            assignment_group=assignment_group,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    except TicketServiceError as exc:
        logger.exception("Admin tickets could not be listed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tickets are unavailable.",
        ) from exc


@router.get("/tickets/{ticket_id}", response_model=AdminTicketDetail)
def admin_get_ticket(
    ticket_id: str,
    service: TicketService = Depends(get_admin_ticket_service),
) -> AdminTicketDetail:
    try:
        return service.get_admin_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc
    except TicketServiceError as exc:
        logger.exception("Admin ticket details could not be loaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ticket details are unavailable.",
        ) from exc


@router.put("/tickets/{ticket_id}/status", response_model=Ticket)
def admin_update_ticket_status(
    ticket_id: str,
    request: TicketStatusUpdateRequest,
    service: TicketService = Depends(get_admin_ticket_service),
) -> Ticket:
    try:
        return service.update_ticket(
            ticket_id,
            TicketUpdateRequest(status=request.status),
            actor=request.actor,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc
    except (TicketServiceError, ValueError) as exc:
        logger.exception("Ticket status could not be updated")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket status could not be updated.",
        ) from exc


@router.put("/tickets/{ticket_id}/assign", response_model=Ticket)
def admin_assign_ticket(
    ticket_id: str,
    request: TicketAssignmentRequest,
    service: TicketService = Depends(get_admin_ticket_service),
) -> Ticket:
    if request.assigned_group not in ADMIN_ASSIGNMENT_GROUPS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported assignment group.",
        )
    try:
        return service.assign_ticket(
            ticket_id,
            request.assigned_group,
            actor=request.actor,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc
    except (TicketServiceError, ValueError) as exc:
        logger.exception("Ticket assignment could not be updated")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket assignment could not be updated.",
        ) from exc


@router.post(
    "/tickets/{ticket_id}/comments",
    response_model=TicketComment,
    status_code=status.HTTP_201_CREATED,
)
def admin_add_ticket_comment(
    ticket_id: str,
    request: TicketCommentCreateRequest,
    service: TicketService = Depends(get_admin_ticket_service),
) -> TicketComment:
    try:
        return service.add_ticket_comment(ticket_id, request.body, request.author)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc
    except TicketServiceError as exc:
        logger.exception("Ticket comment could not be added")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The comment could not be added.",
        ) from exc


@router.get("/tickets/{ticket_id}/comments", response_model=list[TicketComment])
def admin_list_ticket_comments(
    ticket_id: str,
    service: TicketService = Depends(get_admin_ticket_service),
) -> list[TicketComment]:
    try:
        return service.list_ticket_comments(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc
    except TicketServiceError as exc:
        logger.exception("Ticket comments could not be loaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ticket comments are unavailable.",
        ) from exc


@router.get("/analytics")
def admin_ticket_analytics(
    service: TicketService = Depends(get_admin_ticket_service),
) -> dict[str, object]:
    try:
        return service.get_analytics()
    except TicketServiceError as exc:
        logger.exception("Ticket analytics could not be loaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ticket analytics are unavailable.",
        ) from exc
