from pathlib import Path
from langchain_community import PyPDFLoader
from langchain_core.documents import Document


def load_pdf_as_single_document(pdf_path: str | Path) -> list[Document]: 
    resolved_pdf_path = Path(pdf_path).resolve()
    
    if not resolved_pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {resolved_pdf_path}")
        
    if resolved_pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a file PDF file, got: {resolved_pdf_path.name}")
    
    loader = PyPDFLoader(str(resolved_pdf_path), mode="single")
    documents = loader.load()
    
    if not documents:
        raise ValueError(f"No content was loaded from PDF: {resolved_pdf_path}")
                         
    return documents
    