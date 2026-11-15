from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IncidentCategory = Literal[
    "Network",
    "Software",
    "Hardware",
    "Email",
    "Access Management",
    "Security",
    "Database",
    "Cloud",
    "Collaboration Tools",
]
IncidentPriority = Literal["Critical", "High", "Medium", "Low"]
IncidentImpact = Literal["Single User", "Multiple Users", "Department", "Organization"]


class ClassificationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=4000)


class IncidentClassification(BaseModel):
    issue: str = Field(min_length=1)
    category: IncidentCategory
    subcategory: str = Field(min_length=1)
    priority: IncidentPriority
    impact: IncidentImpact
    assigned_group: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)
