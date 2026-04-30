from pathlib import Path
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from app.core.config import settings


EMBEDDING_MODEL_NAME = settings.embedding_model_name

def create_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

def build_faiss_vector_store(documents: list[Document]) -> FAISS:
    if not documents:
        raise ValueError("No documents were provided to build the FAISS vector store")
    
    embedding_model = create_embedding_model()
    vector_store = FAISS.from_documents(documents, embedding_model)
    
    return vector_store

def save_faiss_vector_store(vector_store: FAISS, index_path: str | Path) -> None:
    resolved_index_path = Path(index_path).resolve()
    resolved_index_path.parent.mkdir(parents=True, exist_ok=True)
    
    vector_store.save_local(str(resolved_index_path))
    
def load_faiss_vector_store(index_path: str | Path) -> FAISS:
    resolved_index_path = Path(index_path).resolve()
    
    if not resolved_index_path.exists():
        raise FileNotFoundError(f"FAISS index directory not found: {resolved_index_path}")
    
    embedding_model = create_embedding_model()
    vector_store = FAISS.load_local(
        str(resolved_index_path),
        embedding_model,
        allow_dangerous_deserialization=True
    )
    
    return vector_store
