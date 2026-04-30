from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question")
    
class ChatSource(BaseModel):
    excerpt: str = Field(..., description="A short preview of the retrieve source chunk.")
    score: float = Field(..., description="The similarity score returned by the vector store.")
    
class ChatResponse(BaseModel):
    answer: str = Field(..., description="The generated answer based on retrieved context")
    sources: list[ChatSource] = Field(
        default_factory=list,
        description="Retrieved source chunks used to answer the question."
    )   