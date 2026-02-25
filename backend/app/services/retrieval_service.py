import os
from supabase import create_client

from .embedding_service import embed_text

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


async def search(query: str, top_k: int = 5, doc_type_filter: str | None = None) -> list[dict]:
    """Vector similarity search using pgvector cosine distance via Supabase RPC.

    Searches the global corpus (all users' documents) — see Migration 011.
    Fetches a larger candidate pool then applies per-document diversity so that
    chunks from multiple documents are always represented in the context.
    """
    query_embedding = await embed_text(query)

    # Fetch a wider pool to ensure multi-document coverage
    candidate_count = top_k * 4
    params = {
        "query_embedding": query_embedding,
        "match_count": candidate_count,
    }
    if doc_type_filter:
        params["filter_doc_type"] = doc_type_filter

    result = supabase.rpc("match_document_chunks", params).execute()
    candidates = result.data or []

    # Per-document cap: max 3 chunks per source, round-robin across documents
    # until we have top_k chunks. This guarantees all retrieved documents get
    # at least some representation in the context window.
    per_doc_limit = 3
    buckets: dict[str, list[dict]] = {}
    for chunk in candidates:
        key = chunk.get("doc_filename", "unknown")
        buckets.setdefault(key, [])
        if len(buckets[key]) < per_doc_limit:
            buckets[key].append(chunk)

    # Interleave: take one chunk from each doc in round-robin order (by best similarity)
    diverse: list[dict] = []
    sources = list(buckets.values())
    i = 0
    while len(diverse) < top_k and sources:
        idx = i % len(sources)
        bucket = sources[idx]
        if bucket:
            diverse.append(bucket.pop(0))
        if not bucket:
            sources.pop(idx)
        else:
            i += 1

    return diverse


async def fetch_all_chunks_by_document() -> dict[str, list[dict]]:
    """Fetch all document chunks from the global corpus, grouped by document_id."""
    result = supabase.table("document_chunks").select(
        "id, content, doc_filename, chunk_index, document_id, doc_metadata"
    ).execute()

    chunks_by_doc: dict[str, list[dict]] = {}
    for chunk in result.data or []:
        doc_id = chunk["document_id"]
        if doc_id not in chunks_by_doc:
            chunks_by_doc[doc_id] = []
        chunks_by_doc[doc_id].append(chunk)

    return chunks_by_doc
