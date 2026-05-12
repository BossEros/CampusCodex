from pathlib import Path
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_core.documents import Document


def _attach_page_metadata(documents: list[Document]) -> list[Document]:
    normalized_documents: list[Document] = []

    for index, document in enumerate(documents):
        metadata = dict(document.metadata)

        # Keep a consistent zero-based page field for internal use, plus a
        # one-based page_number value for easier display/debugging.
        page_value = metadata.get("page")
        if page_value is None:
            page_value = metadata.get("page_number")

        try:
            zero_based_page = int(page_value)
            if metadata.get("page") is None and metadata.get("page_number") is not None:
                zero_based_page -= 1
        except (TypeError, ValueError):
            zero_based_page = index

        metadata["page"] = zero_based_page
        metadata["page_number"] = zero_based_page + 1
        normalized_documents.append(
            Document(page_content=document.page_content, metadata=metadata)
        )

    return normalized_documents


def load_pdf_documents_with_page_metadata(pdf_path: str | Path) -> list[Document]:
    resolved_pdf_path = Path(pdf_path).resolve()
    
    if not resolved_pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {resolved_pdf_path}")
        
    if resolved_pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a file PDF file, got: {resolved_pdf_path.name}")
    
    loader = PDFPlumberLoader(str(resolved_pdf_path))
    documents = loader.load()
    
    if not documents:
        raise ValueError(f"No content was loaded from PDF: {resolved_pdf_path}")

    return _attach_page_metadata(documents)


def load_pdf_as_single_document(pdf_path: str | Path) -> list[Document]:
    return load_pdf_documents_with_page_metadata(pdf_path)
