from pathlib import Path
import shutil
import sys

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.rag.pdf_loader import load_pdf_documents_with_page_metadata
from app.rag.text_chunker import split_documents_into_chunks
from app.rag.vector_store import (build_faiss_vector_store, save_faiss_vector_store)


def print_sample_chunks(chunks: list, sample_size: int = 3) -> None:
    if not chunks:
        print("No chunk available for preview")
        return
    
    sample_indexes = [0, len(chunks) // 2, len(chunks) - 1]
    seen_indexes: list[int] = []
    
    print("\nSample chunks")
    for index in sample_indexes:
        if index in seen_indexes:
            continue
        
        seen_indexes.append(index)
        chunk = chunks[index]
        preview = chunk.page_content[:250].replace("\n", " ").strip()
        page_number = chunk.metadata.get("page")
        
        print(f"\nChunk #{index}")
        print(f"Source: {chunk.metadata.get('source', 'unknown')}")
        if page_number is not None:
            print(f"Page: {int(page_number) + 1}")
        print(f"Preview: {preview}")

def main() -> None:
    pdf_path = Path(settings.pdf_path)
    index_path = Path(settings.faiss_index_path)
    
    print("Loading PDF...")
    documents = load_pdf_documents_with_page_metadata(pdf_path)
    print(f"Loaded documents: {len(documents)}")
    
    print("Splitting documents into chunks...")
    chunks = split_documents_into_chunks(documents)
    print(f"Built chunks: {len(chunks)}")

    print_sample_chunks(chunks)
    print("\nNote: page-level metadata is preserved because PDFPlumberLoader loads page documents.")

    print("\nBuilding FAISS vector store...")
    vector_store = build_faiss_vector_store(chunks)

    if index_path.exists():
        shutil.rmtree(index_path)

    print(f"Saving FAISS index to: {index_path}")
    save_faiss_vector_store(vector_store, index_path)

    print("\nIndex build completed successfully.")


if __name__ == "__main__":
    main()
