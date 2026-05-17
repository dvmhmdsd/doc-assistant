"""Prometheus metrics for the doc assistant."""
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

# Use a dedicated registry so tests can import cleanly
REGISTRY = CollectorRegistry()

ingest_seconds = Histogram(
    "doc_assistant_ingest_seconds",
    "Time taken for document ingestion stages",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60),
    registry=REGISTRY,
)

retrieval_seconds = Histogram(
    "doc_assistant_retrieval_seconds",
    "Time taken for retrieval queries",
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1, 2),
    registry=REGISTRY,
)

time_to_first_token_seconds = Histogram(
    "doc_assistant_time_to_first_token_seconds",
    "Time from /ask request to first token emitted",
    buckets=(0.01, 0.1, 0.5, 1, 2, 5),
    registry=REGISTRY,
)

stream_total_seconds = Histogram(
    "doc_assistant_stream_total_seconds",
    "Total stream duration for /ask",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30),
    registry=REGISTRY,
)

provider_retry_total = Counter(
    "doc_assistant_provider_retry_total",
    "Provider retry count by provider",
    labelnames=("provider",),
    registry=REGISTRY,
)


def metrics_latest() -> bytes:
    return generate_latest(REGISTRY)
