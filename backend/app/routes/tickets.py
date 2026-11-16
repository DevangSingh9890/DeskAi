import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.models.ticket import (
    SimilarTicket,
    Ticket,
    TicketApprovalRequest,
    TicketApprovalResponse,
    TicketCreateRequest,
    TicketStatusResponse,
    TicketUpdateRequest,
)
from app.services.ticket_service import (
    PendingApprovalNotFoundError,
    TicketNotFoundError,
    TicketServiceError,
    ticket_service,
)
from app.tools.assign_ticket import assign_ticket_tool
from app.tools.create_ticket import create_ticket_tool
from app.tools.get_ticket_status import get_ticket_status_tool
from app.tools.search_similar_tickets import search_similar_tickets_tool
from app.tools.update_ticket import update_ticket_tool

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/tickets", response_model=Ticket, status_code=status.HTTP_201_CREATED)
def create_ticket(request: TicketCreateRequest) -> Ticket:
    try:
        created = create_ticket_tool.invoke(request.model_dump())
    except (TicketServiceError, ValueError) as exc:
        logger.exception("Ticket creation failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The ticket could not be created.",
        ) from exc
    return Ticket.model_validate(created)


@router.post("/tickets/approve", response_model=TicketApprovalResponse)
def approve_ticket(request: TicketApprovalRequest) -> TicketApprovalResponse:
    if not request.approved:
        try:
            ticket_service.reject_ticket_approval(
                request.approval_id,
                request.message,
            )
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
        created = create_ticket_tool.invoke(
            {
                "approval_id": request.approval_id,
                "message": request.message,
            }
        )
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
        created = ticket_service.create_ticket(request.ticket_details)
    except (TicketServiceError, ValueError) as exc:
        logger.exception("Approved ticket creation failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The approved ticket could not be created.",
        ) from exc

    ticket = Ticket.model_validate(created)
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
) -> list[SimilarTicket]:
    try:
        results = search_similar_tickets_tool.invoke(
            {
                "query": q,
                "category": category,
                "priority": priority,
                "limit": limit,
            }
        )
    except (TicketServiceError, ValueError) as exc:
        logger.exception("Similar ticket search failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Similar tickets are unavailable.",
        ) from exc
    return [SimilarTicket.model_validate(result) for result in results]


@router.get(
    "/tickets/status/{ticket_id}",
    response_model=TicketStatusResponse,
)
def get_ticket_status(ticket_id: str) -> TicketStatusResponse:
    try:
        result = get_ticket_status_tool.invoke({"ticket_id": ticket_id})
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc
    return TicketStatusResponse.model_validate(result)


@router.get("/tickets", response_model=list[Ticket])
def list_tickets() -> list[Ticket]:
    return ticket_service.list_tickets()


@router.get("/tickets/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: str) -> Ticket:
    try:
        return ticket_service.get_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket was not found.",
        ) from exc


@router.put("/tickets/{ticket_id}", response_model=Ticket)
def update_ticket(ticket_id: str, request: TicketUpdateRequest) -> Ticket:
    if not request.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one ticket field must be provided.",
        )

    try:
        changes: dict[str, Any] = request.model_dump(exclude_unset=True)
        if set(changes) == {"assigned_group"}:
            updated = assign_ticket_tool.invoke(
                {
                    "ticket_id": ticket_id,
                    "assigned_group": changes["assigned_group"],
                }
            )
        else:
            updated = update_ticket_tool.invoke(
                {"ticket_id": ticket_id, "updates": changes}
            )
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
    return Ticket.model_validate(updated)
