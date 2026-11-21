import logging
import secrets

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import HumanChatMessageRecord, HumanConversationRecord
from app.database.session import get_db
from app.models.handoff import (
    HandoffAcceptRequest,
    HandoffConversationDetail,
    HandoffConversationResponse,
    HandoffMessageResponse,
    HandoffQueueItem,
    HandoffRequest,
    HandoffSendMessageRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/handoff", tags=["human support"])


def _find_conversation(
    database: Session, conversation_id: str
) -> HumanConversationRecord:
    conversation = database.scalar(
        select(HumanConversationRecord).where(
            HumanConversationRecord.conversation_id == conversation_id
        )
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Human support conversation was not found.",
        )
    return conversation


@router.post(
    "/request",
    response_model=HandoffConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_handoff_request(
    request: HandoffRequest,
    database: Session = Depends(get_db),
) -> HumanConversationRecord:
    latest_user_message = next(
        (message for message in reversed(request.messages) if message.role == "user"),
        None,
    )
    if latest_user_message is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The conversation must contain a user message.",
        )

    conversation = HumanConversationRecord(
        conversation_id=f"HUM-{secrets.token_hex(4).upper()}",
        status="Pending",
        ticket_id=request.ticket_id,
        priority=request.priority,
        category=request.category,
        context={
            **request.context,
            "conversation_history": [
                message.model_dump(mode="json") for message in request.messages
            ],
        },
    )
    database.add(conversation)
    try:
        database.flush()
        for message in request.messages:
            database.add(
                HumanChatMessageRecord(
                    conversation_id=conversation.conversation_id,
                    sender_type="user" if message.role == "user" else "agent",
                    message=message.content,
                    **(
                        {"created_at": message.timestamp}
                        if message.timestamp is not None
                        else {}
                    ),
                )
            )
        database.add(
            HumanChatMessageRecord(
                conversation_id=conversation.conversation_id,
                sender_type="system",
                message="Human support request created. Waiting for a support engineer.",
            )
        )
        database.commit()
        database.refresh(conversation)
    except Exception:
        database.rollback()
        logger.exception("Could not create human support request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The human support request could not be created.",
        )
    return conversation


@router.get("/requests", response_model=list[HandoffQueueItem])
def list_handoff_requests(
    status_filter: str | None = Query(default=None, alias="status", max_length=40),
    database: Session = Depends(get_db),
) -> list[HumanConversationRecord]:
    statement = select(HumanConversationRecord).order_by(
        HumanConversationRecord.created_at.desc()
    )
    if status_filter:
        statement = statement.where(HumanConversationRecord.status == status_filter)
    return list(database.scalars(statement).all())


@router.post(
    "/{conversation_id}/accept", response_model=HandoffConversationResponse
)
def accept_handoff_request(
    conversation_id: str,
    request: HandoffAcceptRequest = Body(default=HandoffAcceptRequest()),
    database: Session = Depends(get_db),
) -> HumanConversationRecord:
    conversation = _find_conversation(database, conversation_id)
    if conversation.status in {"Resolved", "Closed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A resolved or closed conversation cannot be accepted.",
        )
    if conversation.status in {"Pending", "Waiting"}:
        conversation.status = "Assigned"
        conversation.assigned_agent = request.agent_name
        database.add(
            HumanChatMessageRecord(
                conversation_id=conversation_id,
                sender_type="system",
                message=f"{request.agent_name} accepted this conversation.",
            )
        )
        try:
            database.commit()
        except Exception:
            database.rollback()
            logger.exception(
                "Could not assign human support conversation id=%s", conversation_id
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The conversation could not be accepted.",
            )
    if conversation.status == "Assigned":
        conversation.status = "In Progress"
        try:
            database.commit()
            database.refresh(conversation)
        except Exception:
            database.rollback()
            logger.exception(
                "Could not accept human support conversation id=%s", conversation_id
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The conversation could not be accepted.",
            )
    return conversation


@router.get(
    "/{conversation_id}/messages", response_model=HandoffConversationDetail
)
def get_handoff_messages(
    conversation_id: str,
    database: Session = Depends(get_db),
) -> HandoffConversationDetail:
    conversation = _find_conversation(database, conversation_id)
    messages = database.scalars(
        select(HumanChatMessageRecord)
        .where(HumanChatMessageRecord.conversation_id == conversation_id)
        .order_by(HumanChatMessageRecord.created_at, HumanChatMessageRecord.id)
    ).all()
    return HandoffConversationDetail(
        conversation=conversation,
        messages=messages,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=HandoffMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_handoff_message(
    conversation_id: str,
    request: HandoffSendMessageRequest,
    database: Session = Depends(get_db),
) -> HumanChatMessageRecord:
    conversation = _find_conversation(database, conversation_id)
    if conversation.status in {"Resolved", "Closed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Messages cannot be sent to a resolved or closed conversation.",
        )
    if request.sender_type == "agent" and conversation.status in {
        "Pending",
        "Waiting",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accept the conversation before replying as a support engineer.",
        )
    message = HumanChatMessageRecord(
        conversation_id=conversation_id,
        sender_type=request.sender_type,
        message=request.message,
    )
    database.add(message)
    if request.sender_type == "agent":
        conversation.status = "In Progress"
    try:
        database.commit()
        database.refresh(message)
    except Exception:
        database.rollback()
        logger.exception(
            "Could not save human support message id=%s", conversation_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The message could not be sent.",
        )
    return message


@router.get("/{conversation_id}/status", response_model=HandoffConversationResponse)
def get_handoff_status(
    conversation_id: str,
    database: Session = Depends(get_db),
) -> HumanConversationRecord:
    return _find_conversation(database, conversation_id)


@router.post(
    "/{conversation_id}/resolve", response_model=HandoffConversationResponse
)
def resolve_handoff_request(
    conversation_id: str,
    database: Session = Depends(get_db),
) -> HumanConversationRecord:
    conversation = _find_conversation(database, conversation_id)
    if conversation.status in {"Pending", "Waiting"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accept the conversation before resolving it.",
        )
    if conversation.status == "Closed":
        return conversation
    conversation.status = "Resolved"
    try:
        database.flush()
        conversation.status = "Closed"
        database.add(
            HumanChatMessageRecord(
                conversation_id=conversation_id,
                sender_type="system",
                message="This human support conversation was resolved and closed.",
            )
        )
        database.commit()
        database.refresh(conversation)
    except Exception:
        database.rollback()
        logger.exception("Could not resolve human support id=%s", conversation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The conversation could not be resolved.",
        )
    return conversation
