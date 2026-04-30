from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_documents_into_chunks(documents:  list[Document]) -> list[Document]:
    if not documents:
        raise ValueError("No documents were provided for chunking")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 800,
        chunk_overlap = 120,
    )
    
    chunked_documents = text_splitter.split_documents(documents)
    
    if not chunked_documents:
        raise ValueError("No chunks were created from the provided documents.")
    
    return chunked_documents
    