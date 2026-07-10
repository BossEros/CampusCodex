from typing import Any, Callable
import time

# Voyage's free/no-payment-method tier caps requests at a low RPM/TPM budget
# (see backend/app/scripts/seed_pinecone_corpus.py for the same constraint).
# The eval harness calls Voyage both for retrieval query embeddings and,
# via the RAGAS judge, for answer_relevancy scoring — both call sites need
# the same resilience.
EMBEDDING_RATE_LIMIT_RETRY_DELAY_SECONDS = 75
EMBEDDING_RATE_LIMIT_MAX_RETRIES = 6


def call_with_voyage_rate_limit_retry(call: Callable[[], Any]) -> Any:
    from voyageai.error import RateLimitError

    for attempt in range(1, EMBEDDING_RATE_LIMIT_MAX_RETRIES + 1):
        try:
            return call()
        except RateLimitError:
            if attempt == EMBEDDING_RATE_LIMIT_MAX_RETRIES:
                raise

            print(
                f"Voyage rate limited (attempt {attempt}/{EMBEDDING_RATE_LIMIT_MAX_RETRIES}); "
                f"waiting {EMBEDDING_RATE_LIMIT_RETRY_DELAY_SECONDS}s before retrying..."
            )
            time.sleep(EMBEDDING_RATE_LIMIT_RETRY_DELAY_SECONDS)

    raise AssertionError("unreachable")
