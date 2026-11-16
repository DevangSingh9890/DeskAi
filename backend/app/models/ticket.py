from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
