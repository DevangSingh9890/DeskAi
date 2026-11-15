from pydantic import BaseModel, ConfigDict, Field


class SemanticSearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=20)


class SearchResult(BaseModel):
    content: str
    metadata: dict[str, str | int | float | bool]
    score: float


class SemanticSearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class KnowledgeBaseStats(BaseModel):
    total_indexed_documents: int | None
    total_indexed_chunks: int | None
    collection_name: str
    vector_database_available: bool
    error: str | None = None
