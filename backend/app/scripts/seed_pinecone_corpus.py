from pathlib import Path
import argparse
import json
import sys
import time

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.embeddings.factory import create_embedding_provider
from app.rag.pdf_loader import load_pdf_documents_with_page_metadata
from app.rag.text_chunker import split_documents_into_chunks
from app.rag.vector_store import create_pinecone_client
from langchain_core.documents import Document

CORPUS_TITLE = "Student Manual 2019"
# Voyage's free/no-payment-method tier caps requests at a low RPM and TPM
# budget. Batches are kept small and spaced out, with backoff-and-retry on
# rate-limit errors, since the exact effective limit is not documented
# precisely enough to compute a batch size that never trips it.
EMBEDDING_BATCH_SIZE = 20
EMBEDDING_REQUEST_DELAY_SECONDS = 75
EMBEDDING_RATE_LIMIT_RETRY_DELAY_SECONDS = 75
EMBEDDING_RATE_LIMIT_MAX_RETRIES = 6
UPSERT_BATCH_SIZE = 100
EMBEDDING_CACHE_PATH = BACKEND_DIR.parent / "data" / "cache" / "voyage_chunk_embeddings.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the student manual corpus into one or more Pinecone namespaces.",
    )
    parser.add_argument(
        "--namespaces",
        nargs="+",
        default=[settings.pinecone_benchmark_namespace, settings.pinecone_shared_namespace],
        help=(
            "Pinecone namespaces to seed. Defaults to both the benchmark namespace and the "
            "shared_kb namespace, since the project currently has a single canonical corpus "
            "and no separate admin-uploaded content yet. Pass a single namespace to seed only "
            "the benchmark or only shared_kb."
        ),
    )
    return parser.parse_args()


def build_chunk_metadata(chunk: Document, chunk_index: int) -> dict:
    return {
        "title": CORPUS_TITLE,
        "source": str(chunk.metadata.get("source", "")),
        "page": int(chunk.metadata["page"]),
        "page_number": int(chunk.metadata["page_number"]),
        "chunk_text": chunk.page_content,
        "chunk_index": chunk_index,
    }


def build_chunk_vector_id(namespace: str, chunk_index: int) -> str:
    return f"{namespace}-student-manual-chunk-{chunk_index}"


def batched(items: list, batch_size: int):
    for start_index in range(0, len(items), batch_size):
        yield items[start_index : start_index + batch_size]


def compute_corpus_fingerprint(chunks: list[Document]) -> str:
    import hashlib

    hasher = hashlib.sha256()
    for chunk in chunks:
        hasher.update(chunk.page_content.encode("utf-8"))

    return hasher.hexdigest()


def load_cached_embeddings(chunks: list[Document]) -> list[list[float]]:
    if not EMBEDDING_CACHE_PATH.exists():
        return []

    cache_payload = json.loads(EMBEDDING_CACHE_PATH.read_text(encoding="utf-8"))
    cached_embeddings = cache_payload.get("embeddings", [])
    is_same_corpus = cache_payload.get("corpus_fingerprint") == compute_corpus_fingerprint(chunks)

    if not is_same_corpus or len(cached_embeddings) > len(chunks):
        return []

    return cached_embeddings


def save_cached_embeddings(embeddings: list[list[float]], chunks: list[Document]) -> None:
    EMBEDDING_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache_payload = {
        "corpus_fingerprint": compute_corpus_fingerprint(chunks),
        "embeddings": embeddings,
    }
    EMBEDDING_CACHE_PATH.write_text(json.dumps(cache_payload), encoding="utf-8")


def embed_batch_with_retry(batch_texts: list[str], embedding_provider) -> list[list[float]]:
    from voyageai.error import RateLimitError

    for attempt in range(1, EMBEDDING_RATE_LIMIT_MAX_RETRIES + 1):
        try:
            return embedding_provider.embed_documents(batch_texts)
        except RateLimitError:
            if attempt == EMBEDDING_RATE_LIMIT_MAX_RETRIES:
                raise

            print(
                f"Rate limited (attempt {attempt}/{EMBEDDING_RATE_LIMIT_MAX_RETRIES}); "
                f"waiting {EMBEDDING_RATE_LIMIT_RETRY_DELAY_SECONDS}s before retrying..."
            )
            time.sleep(EMBEDDING_RATE_LIMIT_RETRY_DELAY_SECONDS)

    raise AssertionError("unreachable")


def embed_chunks(chunks: list[Document], embedding_provider) -> list[list[float]]:
    embeddings = load_cached_embeddings(chunks)
    if embeddings:
        print(f"Resuming from cache: {len(embeddings)}/{len(chunks)} chunks already embedded.")

    remaining_chunks = chunks[len(embeddings):]
    chunk_batches = list(batched(remaining_chunks, EMBEDDING_BATCH_SIZE))

    for batch_index, chunk_batch in enumerate(chunk_batches):
        print(
            f"Embedding batch {batch_index + 1}/{len(chunk_batches)} "
            f"({len(embeddings)}/{len(chunks)} done so far)..."
        )
        batch_texts = [chunk.page_content for chunk in chunk_batch]
        embeddings.extend(embed_batch_with_retry(batch_texts, embedding_provider))
        save_cached_embeddings(embeddings, chunks)

        is_last_batch = batch_index == len(chunk_batches) - 1
        if not is_last_batch:
            time.sleep(EMBEDDING_REQUEST_DELAY_SECONDS)

    return embeddings


def seed_namespace(
    index_client,
    namespace: str,
    chunks: list[Document],
    embeddings: list[list[float]],
) -> None:
    vectors = [
        {
            "id": build_chunk_vector_id(namespace, chunk_index),
            "values": embedding,
            "metadata": build_chunk_metadata(chunk, chunk_index),
        }
        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    print(f"Upserting {len(vectors)} vectors into namespace '{namespace}'...")
    for vector_batch in batched(vectors, UPSERT_BATCH_SIZE):
        index_client.upsert(vectors=vector_batch, namespace=namespace)

    print(f"Finished seeding namespace '{namespace}'.")


def main() -> None:
    args = parse_args()

    print("Loading PDF...")
    documents = load_pdf_documents_with_page_metadata(settings.pdf_path)
    print(f"Loaded documents: {len(documents)}")

    print("Splitting documents into chunks...")
    chunks = split_documents_into_chunks(documents)
    print(f"Built chunks: {len(chunks)}")

    print("Embedding chunks with the configured embedding provider...")
    embedding_provider = create_embedding_provider()
    embeddings = embed_chunks(chunks, embedding_provider)
    print(f"Embedded {len(embeddings)} chunks.")

    pinecone_client = create_pinecone_client()
    index_client = pinecone_client.Index(settings.pinecone_index_name)

    for namespace in args.namespaces:
        seed_namespace(index_client, namespace, chunks, embeddings)

    print("\nPinecone corpus seeding completed successfully.")


if __name__ == "__main__":
    main()
