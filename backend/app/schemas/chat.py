from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(
        ...,
        description="The speaker for a chat history message.",
    )
    content: str = Field(..., min_length=1, description="The message content.")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question")
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Recent chat history used to understand follow-up questions.",
    )


class ChatSource(BaseModel):
    excerpt: str = Field(..., description="A short preview of the retrieve source chunk.")
    score: float = Field(..., description="The reranker relevance score.")
    page_number: int | None = Field(
        default=None,
        description="One-based page number for the retrieved source chunk, when available."
    )
    source: str | None = Field(
        default=None,
        description="Source PDF path for the retrieved source chunk, when available."
    )
    
class ChatResponse(BaseModel):
    answer: str = Field(..., description="The generated answer based on retrieved context")
    sources: list[ChatSource] = Field(
        default_factory=list,
        description="Retrieved source chunks used to answer the question."
    )
