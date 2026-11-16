import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.ticket import (
    SimilarTicket,
    Ticket,
    TicketApprovalRequest,
    TicketApprovalResponse,
    TicketCreateRequest,
    TicketStatusResponse,
    TicketUpdateRequest,
)
from app.repositories.ticket_repository import TicketRepository
from app.services.ticket_service import (
    PendingApprovalNotFoundError,
    TicketNotFoundError,
    TicketService,
    TicketServiceError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_ticket_service(database: Session = Depends(get_db)) -> TicketService:
    return TicketService(TicketRepository(database))


@router.post("/tickets", response_model=Ticket, status_code=status.HTTP_201_CREATED)
def create_ticket(
    request: TicketCreateRequest,
    service: TicketService = Depends(get_ticket_service),
) -> Ticket:
    try:
        return service.create_ticket(request)
    except (TicketServiceError, ValueError) as exc:
        logger.exception("Ticket creation failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The ticket could not be created.",
        ) from exc


@router.post("/tickets/approve", response_model=TicketApprovalResponse)
def approve_ticket(
    request: TicketApprovalRequest,
    service: TicketService = Depends(get_ticket_service),
) -> TicketApprovalResponse:
    if not request.approved:
        try:
            service.reject_ticket_approval(request.approval_id, request.message)
        except PendingApprovalNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pending ticket recommendation matches this request.",
            ) from exc
        logger.info("Ticket recommendation rejected")
        return TicketApprovalResponse(
            approved=False,
            status="Rejected",
            message="Ticket recommendation declined.",
        )

    try:
        ticket = service.approve_ticket(request.approval_id, request.message)
    except PendingApprovalNotFoundError as exc:
        if (
            request.ticket_details is None
            or request.ticket_details.description != request.message
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The pending approval expired or is unavailable. "
                    "Submit the incident again to request a new approval."
                ),
            ) from exc
        logger.warning(
            "Pending approval unavailable; honoring explicit approval with "
            "the submitted ticket details"
        )
        try:
            ticket = service.create_ticket(request.ticket_details)
        except (TicketServiceError, ValueError) as create_exc:
            logger.exception("Approved ticket creation failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The approved ticket could not be created.",
            ) from create_exc
    except (TicketServiceError, ValueError) as exc:
        logger.exception("Approved ticket creation failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The approved ticket could not be created.",
        ) from exc

    return TicketApprovalResponse(
        approved=True,
        ticket_id=ticket.ticket_id,
        status=ticket.status,
        assigned_group=ticket.assigned_group,
        ticket=ticket,
    )


@router.get("/tickets/similar", response_model=list[SimilarTicket])
def search_similar_tickets(
    q: str = Query(min_length=1, max_length=4000),
    category: str | None = Query(default=None, max_length=100),
    priority: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=5, ge=1, le=50),
    service: TicketService = Depends(get_ticket_service),
) -> list[SimilarTicket]:
    try:
        return service.search_similar_tickets(
            q,
            category=category,
            priority=priority,
            limit=limit,
        )
    except (TicketServiceError, ValueError) as exc:
        logger.exception("Similar ticket search failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Similar tickets are unavailable.",
        ) from exc


@router.get("/tickets/status/{ticket_id}", response_model=TicketStatusResponse)
def get_ticket_status(
    ticket_id: str,
    service: TicketService = Depends(get_ticket_service),
) -> TicketStatusResponse:
    try:
        return service.get_ticket_status(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc


@router.get("/tickets", response_model=list[Ticket])
def list_tickets(
    service: TicketService = Depends(get_ticket_service),
) -> list[Ticket]:
    return service.list_tickets()


@router.get("/tickets/{ticket_id}", response_model=Ticket)
def get_ticket(
    ticket_id: str,
    service: TicketService = Depends(get_ticket_service),
) -> Ticket:
    try:
        return service.get_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc


@router.put("/tickets/{ticket_id}", response_model=Ticket)
def update_ticket(
    ticket_id: str,
    request: TicketUpdateRequest,
    service: TicketService = Depends(get_ticket_service),
) -> Ticket:
    if not request.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one ticket field must be provided.",
        )

    try:
        if set(request.model_dump(exclude_unset=True)) == {"assigned_group"}:
            return service.assign_ticket(ticket_id, request.assigned_group or "")
        return service.update_ticket(ticket_id, request)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc
    except (TicketServiceError, ValueError) as exc:
        logger.exception("Ticket update failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The ticket could not be updated.",
        ) from exc


@router.get("/admin/tickets", response_model=list[Ticket])
def admin_list_tickets(
    service: TicketService = Depends(get_ticket_service),
) -> list[Ticket]:
    return service.list_tickets()


@router.get("/admin/tickets/{ticket_id}", response_model=Ticket)
def admin_get_ticket(
    ticket_id: str,
    service: TicketService = Depends(get_ticket_service),
) -> Ticket:
    return get_ticket(ticket_id, service)


@router.put("/admin/tickets/{ticket_id}", response_model=Ticket)
def admin_update_ticket(
    ticket_id: str,
    request: TicketUpdateRequest,
    service: TicketService = Depends(get_ticket_service),
) -> Ticket:
    return update_ticket(ticket_id, request, service)


@router.get("/admin/analytics")
def admin_ticket_analytics(
    service: TicketService = Depends(get_ticket_service),
) -> dict[str, Any]:
    return service.get_analytics()
