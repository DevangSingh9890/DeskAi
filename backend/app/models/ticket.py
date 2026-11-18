from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TicketPriority = Literal["Critical", "High", "Medium", "Low"]
TicketStatus = Literal["Open", "In Progress", "Resolved", "Closed"]


class TicketCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    priority: TicketPriority
    category: str = Field(min_length=1, max_length=100)
    subcategory: str = Field(min_length=1, max_length=100)
    assigned_group: str = Field(min_length=1, max_length=150)
    created_by: str = Field(default="user", min_length=1, max_length=150)
    impact: str | None = Field(default=None, max_length=20)
    ai_recommendation: str | None = Field(default=None, max_length=4000)
    knowledge_sources: list[str] = Field(default_factory=list, max_length=20)
    similar_incidents: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class TicketUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    priority: TicketPriority | None = None
    status: TicketStatus | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    subcategory: str | None = Field(default=None, min_length=1, max_length=100)
    assigned_group: str | None = Field(default=None, min_length=1, max_length=150)
    resolution: str | None = Field(default=None, max_length=10000)


class Ticket(BaseModel):
    ticket_id: str
    title: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    category: str
    subcategory: str
    assigned_group: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    resolution: str | None = None
    impact: str = "Medium"
    ai_recommendation: str | None = None
    knowledge_sources: list[str] = Field(default_factory=list)
    similar_incidents: list[dict[str, Any]] = Field(default_factory=list)


class TicketComment(BaseModel):
    id: int
    ticket_id: str
    author: str
    body: str
    created_at: datetime


class TicketHistory(BaseModel):
    id: int
    ticket_id: str
    event_type: str
    old_value: str | None = None
    new_value: str | None = None
    actor: str
    created_at: datetime


class AdminTicketDetail(Ticket):
    comments: list[TicketComment] = Field(default_factory=list)
    history: list[TicketHistory] = Field(default_factory=list)


class TicketCommentCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    body: str = Field(min_length=1, max_length=5000)
    author: str = Field(default="Service Desk Agent", min_length=1, max_length=150)


class TicketStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TicketStatus
    actor: str = Field(default="Service Desk Agent", min_length=1, max_length=150)


ADMIN_ASSIGNMENT_GROUPS = (
    "Network Support",
    "Hardware Support",
    "Email Support",
    "Identity & Access Management",
    "Security Team",
    "Database Team",
    "Cloud Support",
    "Messaging Team",
)


class TicketAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_group: str = Field(min_length=1, max_length=150)
    actor: str = Field(default="Service Desk Agent", min_length=1, max_length=150)

    @field_validator("assigned_group")
    @classmethod
    def validate_assignment_group(cls, value: str) -> str:
        if value not in ADMIN_ASSIGNMENT_GROUPS:
            raise ValueError("Unsupported assignment group.")
        return value


class TicketApprovalRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    approved: bool
    message: str = Field(min_length=1, max_length=4000)
    approval_id: str | None = Field(default=None, min_length=1, max_length=100)
    ticket_details: TicketCreateRequest | None = None


class TicketApprovalResponse(BaseModel):
    approved: bool
    ticket_id: str | None = None
    status: str
    assigned_group: str | None = None
    ticket: Ticket | None = None
    message: str | None = None


class TicketStatusResponse(BaseModel):
    ticket_id: str
    status: TicketStatus | Literal["Not found"]
    assigned_group: str | None = None
    updated_at: datetime | None = None


class SimilarTicket(BaseModel):
    ticket_id: str
    category: str
    priority: TicketPriority
    summary: str
    resolution: str | None = None


class TicketRecommendation(BaseModel):
    action: Literal[
        "create_ticket",
        "check_ticket_status",
        "find_similar_incidents",
        "no_action",
    ]
    ticket_recommended: bool
    reason: str
    requires_approval: bool
    approval_id: str | None = None
